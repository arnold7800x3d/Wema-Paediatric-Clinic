"""
    file defines the classes that map directly onto the db tables to allow querying and row manipulations as ordinary python objects
"""
from sqlalchemy import Column, String, Time, Integer, Date, ForeignKey, Enum as sqlEnum
from database import Base
import enum

# wemadoctors table in the db
class Doctors(Base):
    __tablename__ = 'wemadoctors'

    doctorid = Column(String, primary_key=True)
    doctorname = Column(String, nullable=False)
    doctoremail = Column(String, nullable=False)
    doctorshiftstart = Column(Time(timezone=False), nullable=False)
    doctorshiftend = Column(Time(timezone=False), nullable=False)

# define the states of valid appointments for the status column
class AppointmentStatus(str, enum.Enum):
    booked = "booked"
    cancelled = "cancelled"

# wemapatients table in the db
class Patient(Base):
    __tablename__ = "wemapatients"

    patientid = Column(Integer, primary_key=True, autoincrement=True)
    patientname = Column(String, nullable=False)
    patientemail = Column(String, nullable=False)

# wemaappointments table in the db
class Appointment(Base):
    __tablename__ = "wemaappointments"

    appointmentid = Column(Integer, primary_key=True, autoincrement=True)
    doctorid = Column(String, ForeignKey("wemadoctors.doctorid"), nullable=False)
    patientid = Column(Integer, ForeignKey("wemapatients.patientid"), nullable=False)
    appointmentdate = Column(Date, nullable=False)
    starttime = Column(Time, nullable=False)
    status = Column(sqlEnum(AppointmentStatus), nullable=False, default=AppointmentStatus.booked)
    cancellationreason =  Column(String, nullable=True)