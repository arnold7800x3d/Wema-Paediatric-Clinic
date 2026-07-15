"""
    file defines what data is allowed in requests and responses
"""
from pydantic import BaseModel
from datetime import time, date

# output schema to display what is shown to a client
class DoctorResponse(BaseModel):
    doctorid: str
    doctorname: str
    doctoremail: str
    doctorshiftstart: time
    doctorshiftend: time

    class Config:
        from_attributes = True

# input schema for booking an appointment
class AppointmentCreate(BaseModel):
    doctorid: str
    patientid: int
    appointmentdate: date
    starttime: time

# output shcema for an appointment used for booking, cancellation and rescheduling
class AppointmentOut(BaseModel):
    appointmentid: int
    doctorid: str
    patientid: int
    appointmentdate: date
    starttime: time
    status: str

    class Config:
        from_attributes = True

# input schema for cancelling an appointment
class AppointmentCancel(BaseModel):
    cancellationreason: str

# input schema for rescheduling an appointment
class AppointmentReschedule(BaseModel):
    newdate: date
    newstarttime: time