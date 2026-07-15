"""
    file that handles everything to do with appointments such as booking, cancelling and rescheduling
"""
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
) # create router object and preprend all routes with /appointment

# route to book appointments
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
        await db.commit() # insert into the db
    except IntegrityError: # if rejected by the partial unique index to safeguard same-time bookings
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This slot has already been booked"
        )
    
    await db.refresh(newAppointment)
    return newAppointment

# route to cancel the appointments
@router.patch("/{id}/cancel", response_model=AppointmentOut)
async def cancelAppointment(id: int, payload: AppointmentCancel, db: AsyncSession = Depends(getDB)):
    # check the appointment exists
    result = await db.execute(select(Appointment).filter(Appointment.appointmentid == id))
    appointment = result.scalar_one_or_none()
    if appointment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Appointment {id} does not exist"
        )
    
    # confirm the appointment is not already cancelled
    if appointment.status == AppointmentStatus.cancelled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Appointment {id} is already cancelled"
        )
    
    # attempt to cancel the appointment
    appointment.status = AppointmentStatus.cancelled
    appointment.cancellationreason = payload.cancellationreason

    await db.commit()
    await db.refresh(appointment)
    return appointment

# route for rescheduling the appointments
@router.patch("/{id}/reschedule", response_model=AppointmentOut)
async def rescheduleAppointment(id: int, payload: AppointmentReschedule, db: AsyncSession = Depends(getDB)):
    # check to ensure the previous appointment actually exists
    result = await db.execute(select(Appointment).filter(Appointment.appointmentid == id))
    oldAppointment = result.scalar_one_or_none()
    if oldAppointment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Appointment {id} does not exist"
        )
    
    # ensure the appointment is not already cancelled, we cannot reschedule something if it is already rejected
    if oldAppointment.status == AppointmentStatus.cancelled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Appointment {id} is cancelled and cannot be rescheduled"
        )
    
    # get the doctor meant to handle the appointment
    doctorResult = await db.execute(select(Doctors).filter(Doctors.doctorid == oldAppointment.doctorid))
    doctor = doctorResult.scalar_one_or_none()

    # get the slots for the doctor and ensure the rescheduled time falls within the doctor's valid slots
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
    
    # change the old row's status to cancelled with a default reason to indicate the appointment has been rescheduled
    oldAppointment.status = AppointmentStatus.cancelled
    oldAppointment.cancellationreason = "Rescheduled to a new slot"

    # register a new appointment and create a new row in the db
    newAppointment = Appointment(
        doctorid = oldAppointment.doctorid,
        patientid = oldAppointment.patientid,
        appointmentdate = payload.newdate,
        starttime = payload.newstarttime,
        status = AppointmentStatus.booked
    )
    db.add(newAppointment)

    # atomicity where the old row's update and creation of the new row are sent to postgres together in a single commit
    try:
        await db.commit()
    except IntegrityError: # still handle a situation where another patient has taken the timeslot
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The new slot has already been booked"
        )
    
    await db.refresh(newAppointment)
    return newAppointment

# bonus route to organize a patient's pending appointments
@router.get("/patients/{id}/appointments", response_model=list[AppointmentOut])
async def getPatientAppointments(id: int, db: AsyncSession = Depends(getDB)):
    # ensure the patient exists
    patientResult = await db.execute(select(Patient).filter(Patient.patientid == id))
    patient = patientResult.scalar_one_or_none()
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient {id} does not exist"
        )
    
    # get the patient's booked appointments for today or later on primarily by date and them by time within the same date
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

    # handle edge case where an appointment is for today but the time has passed
    now = datetime.now()
    upcoming = [
        a for a in appointments
        if datetime.combine(a.appointmentdate, a.starttime) >= now
    ]

    return upcoming