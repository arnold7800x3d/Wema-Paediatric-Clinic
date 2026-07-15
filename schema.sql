CREATE TABLE wemadoctors(
    doctorid VARCHAR(10) PRIMARY KEY,
    doctorname VARCHAR(50) NOT NULL,
    doctoremail VARCHAR(50) NOT NULL,
    doctorshiftstart TIME NOT NULL,
    doctorshiftend TIME NOT NULL
);

INSERT INTO wemadoctors(doctorid, doctorname, doctoremail, doctorshiftstart, doctorshiftend) VALUES
('DR-0001', 'Monkey D Luffy', 'monkeydluffy@wemaclinic.com', '08:00', '10:00'),
('DR-0002', 'Roronoa Zoro', 'roronoazoro@wemaclinic.com', '10:00', '12:00'),
('DR-0003', 'Nico Robin', 'nicorobin@wemaclinic.com', '12:00', '14:00'),
('DR-0004', 'Nami', 'nami@wemaclinic.com', '14:00', '16:00'),
('DR-0005', 'Tony Chopper', 'tonychopper@wemaclinic.com', '16:00', '18:00');

CREATE TYPE appointmentstatus AS ENUM ('booked', 'cancelled');

CREATE TABLE wemapatients(
    patientid SERIAL PRIMARY KEY,
    patientname VARCHAR(50) NOT NULL,
    patientemail VARCHAR(50) NOT NULL
);

INSERT INTO wemapatients (patientname, patientemail)
VALUES ('Vinsmoke Sanji', 'vinsmokesanji@gmail.com')

CREATE TABLE wemaappointments(
    appointmentid SERIAL PRIMARY KEY,
    doctorid VARCHAR(10) NOT NULL REFERENCES wemadoctors(doctorid),
    patientid INT NOT NULL REFERENCES wemapatients(patientid),
    appointmentdate DATE NOT NULL,
    starttime TIME NOT NULL,
    status appointmentstatus NOT NULL DEFAULT 'booked',
    cancellationreason VARCHAR(200),
    UNIQUE (doctorid, appointmentdate, starttime)
);

ALTER TABLE wemaappointments DROP CONSTRAINT wemaappointments_doctorid_appointmentdate_starttime_key;

CREATE UNIQUE INDEX uq_doctor_slot_booked
ON wemaappointments (doctorid, appointmentdate, starttime)
WHERE status = 'booked';