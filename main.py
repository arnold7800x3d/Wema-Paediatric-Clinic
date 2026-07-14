from fastapi import FastAPI
from routers import doctors, appointments

app = FastAPI(title="Wema Paediatric Clinic Booking API")

app.include_router(doctors.router)
app.include_router(appointments.router)

@app.get("/")
async def healthCheck():
    return{
        "status": "OK"          
    }

@app.get("/home")
async def home():
    return{
        "message":"Welcome to Wema Paediatric Clinic, your number 1 hospital to take care of you and your little ones. "
        "We have world-class doctors who are the best in their field and are ready to cater to your needs." 
    }

