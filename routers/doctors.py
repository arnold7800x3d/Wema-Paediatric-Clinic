from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from starlette import status
from datetime import date as dateType
from database import getDB
from models import Doctors, Appointment, AppointmentStatus
from schemas import DoctorResponse
from functions import functionsGeneral

router = APIRouter(
    prefix = "/doctors", tags=["doctors"]
)

@router.get("/{id}", response_model=DoctorResponse, status_code=status.HTTP_200_OK)
async def getDoctorById(id: str, db: AsyncSession = Depends(getDB)):
    result =  await db.execute(select(Doctors).filter(Doctors.doctorid == id))
    doctor = result.scalar_one_or_none()
    if doctor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"The doctor with id {id} you requested for does not exist"
        )
    return doctor

@router.get("/", response_model=list[DoctorResponse])
async def getAllDoctors(db: AsyncSession = Depends(getDB)):
    result = await db.execute(select(Doctors))
    doctors = result.scalars().all()
    return doctors

@router.get("/{id}/availability")
async def getDoctorAvailability(id: str, onDate: dateType, db: AsyncSession = Depends(getDB)):
    result = await db.execute(select(Doctors).filter(Doctors.doctorid == id))
    doctor = result.scalar_one_or_none()
    if doctor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"The doctor with id {id} you requested does not exist"
        )

    totalSlots = functionsGeneral.generateSlots(doctor.doctorshiftstart, doctor.doctorshiftend)
    bookedResult = await db.execute(
        select(Appointment.starttime).filter(
            Appointment.doctorid == id,
            Appointment.appointmentdate == onDate,
            Appointment.status == AppointmentStatus.booked
        )
    )
    bookedTimes = {
        row[0] for row in bookedResult.all()
    }
    availableSlots = [
        s for s in totalSlots if s not in bookedTimes
    ]

    return{
        "doctorid": id,
        "date": onDate,
        "availableSlots": availableSlots
    }