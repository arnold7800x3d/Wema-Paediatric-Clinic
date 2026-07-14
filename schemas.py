from pydantic import BaseModel
from datetime import time, date

class DoctorResponse(BaseModel):
    doctorid: str
    doctorname: str
    doctoremail: str
    doctorshiftstart: time
    doctorshiftend: time

    class Config:
        from_attributes = True

class AppointmentCreate(BaseModel):
    doctorid: str
    patientid: int
    appointmentdate: date
    starttime: time

class AppointmentOut(BaseModel):
    appointmentid: int
    doctorid: str
    patientid: int
    appointmentdate: date
    starttime: time
    status: str

    class Config:
        from_attributes = True

class AppointmentCancel(BaseModel):
    cancellationreason: str

class AppointmentReschedule(BaseModel):
    newdate: date
    newstarttime: time