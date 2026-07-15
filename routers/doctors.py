"""
    file handles everything related to doctors - listing them and their availability
"""
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
) # create router object to ensure routes are prepended with /doctors

# get a single doctor by his/her id
@router.get("/{id}", response_model=DoctorResponse, status_code=status.HTTP_200_OK)
async def getDoctorById(id: str, db: AsyncSession = Depends(getDB)):
    result =  await db.execute(select(Doctors).filter(Doctors.doctorid == id)) # query to match the specific doctor id with the id parameter
    doctor = result.scalar_one_or_none() # return exactly one doctor object if found or none
    if doctor is None: # handle when doctor is not found
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"The doctor with id {id} you requested for does not exist"
        )
    return doctor # return doctor object and convert its shape to that defined by the schema

# get all doctors in the db
@router.get("/", response_model=list[DoctorResponse])
async def getAllDoctors(db: AsyncSession = Depends(getDB)):
    result = await db.execute(select(Doctors)) # query to get all doctors from db
    doctors = result.scalars().all() # unwrap whole result into a list od objects
    return doctors

# get a doctor's availability
@router.get("/{id}/availability")
async def getDoctorAvailability(id: str, onDate: dateType, db: AsyncSession = Depends(getDB)):
    result = await db.execute(select(Doctors).filter(Doctors.doctorid == id)) # first get the doctor by matching their id with that in the db
    doctor = result.scalar_one_or_none()
    if doctor is None: # handle situation when doctor is not found
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"The doctor with id {id} you requested does not exist"
        )

    totalSlots = functionsGeneral.generateSlots(doctor.doctorshiftstart, doctor.doctorshiftend) # generate possible 30 minute slot for the doctor's shift
    bookedResult = await db.execute(
        select(Appointment.starttime).filter(
            Appointment.doctorid == id,
            Appointment.appointmentdate == onDate,
            Appointment.status == AppointmentStatus.booked
        )
    ) # from selecting the starttime column, find the doctor, on a specific date and check their currently booked appointments only
    bookedTimes = {
        row[0] for row in bookedResult.all()
    } # get the time value
    availableSlots = [
        s for s in totalSlots if s not in bookedTimes
    ] # take every generated slot and remove any one which is booked

    return{
        "doctorid": id,
        "date": onDate,
        "availableSlots": availableSlots
    }