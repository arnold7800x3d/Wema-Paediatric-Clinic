from datetime import date, timedelta, datetime

# test if the doctors actually exist in the db
async def test_get_doctors_returns_five(client):
    response = await client.get("/doctors/")
    assert response.status_code == 200
    doctors = response.json()
    assert len(doctors) == 5

# book double appointments
async def test_double_booking_returns_409(client):
    bookingDate = (date.today() + timedelta(days=5)).isoformat()

    payload = {
        "doctorid": "DR-0001",
        "patientid": 1,
        "appointmentdate": bookingDate,
        "starttime": "08:00:00"
    }

    firstResponse = await client.post("/appointments/", json=payload)
    assert firstResponse.status_code == 201
    appointmentid = firstResponse.json()["appointmentid"]

    # attempt same booking as the first to ensure it fails
    try:
        secondResponse = await client.post("/appointments/", json=payload)
        assert secondResponse.status_code == 409
    finally: # cleanup to ensure the db does not fill with test data
        await client.patch(
            f"/appointments/{appointmentid}/cancel",
            json={"cancellationreason": "test cleanup"}
        )

# validation of a doctor's working hours
async def test_booking_outside_working_hours_returns_422(client):
    bookingDate = (date.today() + timedelta(days=5)).isoformat()

    payload = {
        "doctorid": "DR-0001",          # DR-0001 works 08:00-10:00
        "patientid": 1,
        "appointmentdate": bookingDate,
        "starttime": "23:00:00"         # well outside shift hours
    }

    response = await client.post("/appointments/", json=payload)
    assert response.status_code == 422

# test to ensure bookings have to wait for at least an hour
async def test_booking_within_next_hour_returns_422(client):
    # build a datetime 30 minutes from now, then split back into date + time
    nearFuture = datetime.now() + timedelta(minutes=30)

    payload = {
        "doctorid": "DR-0001",
        "patientid": 1,
        "appointmentdate": nearFuture.date().isoformat(),
        "starttime": nearFuture.time().isoformat()
    }

    response = await client.post("/appointments/", json=payload)
    assert response.status_code == 422

# test to ensure a cancelled appointment cannot be cancelled again
async def test_cancel_already_cancelled_returns_409(client):
    bookingDate = (date.today() + timedelta(days=6)).isoformat()

    payload = {
        "doctorid": "DR-0002",          # different doctor/date from other tests to avoids clashing
        "patientid": 1,
        "appointmentdate": bookingDate,
        "starttime": "10:00:00"
    }

    bookingResponse = await client.post("/appointments/", json=payload)
    assert bookingResponse.status_code == 201
    appointmentid = bookingResponse.json()["appointmentid"]

    firstCancel = await client.patch(
        f"/appointments/{appointmentid}/cancel",
        json={"cancellationreason": "test cleanup"}
    )
    assert firstCancel.status_code == 200

    secondCancel = await client.patch(
        f"/appointments/{appointmentid}/cancel",
        json={"cancellationreason": "test cleanup again"}
    )
    assert secondCancel.status_code == 409