from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from starlette import status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from database import getDB
from models import Doctors, Appointment, Patient, AppointmentStatus
from schemas import AppointmentCreate, AppointmentOut, AppointmentCancel, AppointmentReschedule
from functions import functionsGeneral

router = APIRouter(
    prefix="/appointments",
    tags=["appointments"]
)

@router.post("/", response_model=AppointmentOut, status_code=status.HTTP_201_CREATED)
async def bookAppointment(payload: AppointmentCreate, db: AsyncSession = Depends(getDB)):
    # doctor must exist
    doctorResult = await db.execute(select(Doctors).filter(Doctors.doctorid == payload.doctorid))
    doctor = doctorResult.scalar_one_or_none()
    if doctor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Doctor {payload.doctorid} does not exist"
        )
    
    # check patient exists
    patientResult = await db.execute(select(Patient).filter(Patient.patientid == payload.patientid))
    patient = patientResult.scalar_one_or_none()
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient {payload.patientid} does not exist"
        )
    
    # slot must be a valid one within the doctor's shift
    validSlots = functionsGeneral.generateSlots(doctor.doctorshiftstart, doctor.doctorshiftend)
    if payload.starttime not in validSlots:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"{payload.starttime} is not a valid time slot for Dr. {doctor.doctorname}'s working hours "
            f"({doctor.doctorshiftstart}-{doctor.doctorshiftend})"
        )
    
    # requested date and time must not be in the past
    requestedDateTime = datetime.combine(payload.appointmentdate, payload.starttime)
    if requestedDateTime < datetime.now() + timedelta(hours=1):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Appointments must be booked at least 1 hour in advance"
        )
    
    # attempt booking
    newAppointment = Appointment(
        doctorid = payload.doctorid,
        patientid = payload.patientid,
        appointmentdate = payload.appointmentdate,
        starttime = payload.starttime,
        status = AppointmentStatus.booked,
    )
    db.add(newAppointment)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This slot has already been booked"
        )
    
    await db.refresh(newAppointment)
    return newAppointment

@router.patch("/{id}/cancel", response_model=AppointmentOut)
async def cancelAppointment(id: int, payload: AppointmentCancel, db: AsyncSession = Depends(getDB)):
    result = await db.execute(select(Appointment).filter(Appointment.appointmentid == id))
    appointment = result.scalar_one_or_none()
    if appointment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Appointment {id} does not exist"
        )
    
    if appointment.status == AppointmentStatus.cancelled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Appointment {id} is already cancelled"
        )
    
    appointment.status = AppointmentStatus.cancelled
    appointment.cancellationreason = payload.cancellationreason

    await db.commit()
    await db.refresh(appointment)
    return appointment

@router.patch("/{id}/reschedule", response_model=AppointmentOut)
async def rescheduleAppointment(id: int, payload: AppointmentReschedule, db: AsyncSession = Depends(getDB)):
    result = await db.execute(select(Appointment).filter(Appointment.appointmentid == id))
    oldAppointment = result.scalar_one_or_none()
    if oldAppointment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Appointment {id} does not exist"
        )
    
    if oldAppointment.status == AppointmentStatus.cancelled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Appointment {id} is cancelled and cannot be rescheduled"
        )
    
    doctorResult = await db.execute(select(Doctors).filter(Doctors.doctorid == oldAppointment.doctorid))
    doctor = doctorResult.scalar_one_or_none()

    validSlots = functionsGeneral.generateSlots(doctor.doctorshiftstart, doctor.doctorshiftend)
    if payload.newstarttime not in validSlots:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"{payload.newstarttime} is not a valid slot for Dr. {doctor.doctorname}'s working hours"
        )
    
    requestedDateTime = datetime.combine(payload.newdate, payload.newstarttime)
    if requestedDateTime < datetime.now() + timedelta(hours=1):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Appointments must be booked at least 1 hour in advance"
        )
    
    oldAppointment.status = AppointmentStatus.cancelled
    oldAppointment.cancellationreason = "Rescheduled to a new slot"

    newAppointment = Appointment(
        doctorid = oldAppointment.doctorid,
        patientid = oldAppointment.patientid,
        appointmentdate = payload.newdate,
        starttime = payload.newstarttime,
        status = AppointmentStatus.booked
    )
    db.add(newAppointment)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The new slot has already been booked"
        )
    
    await db.refresh(newAppointment)
    return newAppointment

@router.get("/patients/{id}/appointments", response_model=list[AppointmentOut])
async def getPatientAppointments(id: int, db: AsyncSession = Depends(getDB)):
    patientResult = await db.execute(select(Patient).filter(Patient.patientid == id))
    patient = patientResult.scalar_one_or_none()
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient {id} does not exist"
        )
    
    result = await db.execute(
        select(Appointment)
        .filter(
            Appointment.patientid == id,
            Appointment.status == AppointmentStatus.booked,
            Appointment.appointmentdate >= datetime.now().date()
        )
        .order_by(Appointment.appointmentdate, Appointment.starttime)
    )
    appointments = result.scalars().all()

    now = datetime.now()
    upcoming = [
        a for a in appointments
        if datetime.combine(a.appointmentdate, a.starttime) >= now
    ]

    return upcoming