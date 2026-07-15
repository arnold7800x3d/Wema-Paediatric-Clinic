"""
    this file functions as the entry point of the application
"""
from fastapi import FastAPI
from routers import doctors, appointments

app = FastAPI(title="Wema Paediatric Clinic Booking API") # create an instance of the application

# picks routes defined in the router files and mount them in the app
app.include_router(doctors.router)
app.include_router(appointments.router)

@app.get("/") # health check endpoint
async def healthCheck():
    return{
        "status": "OK"          
    }

@app.get("/home") # welcome endpoint
async def home():
    return{
        "message":"Welcome to Wema Paediatric Clinic, your number 1 hospital to take care of you and your little ones. "
        "We have world-class doctors who are the best in their field and are ready to cater to your needs." 
    }

