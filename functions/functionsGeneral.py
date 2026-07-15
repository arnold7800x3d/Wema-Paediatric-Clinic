
"""
    file to get a doctor's slots
"""
from datetime import date, datetime, time, timedelta

def generateSlots(shiftStart: time, shiftEnd: time, slotDuration: int = 30) -> list[time]:
    dummyDate = date.today()
    current = datetime.combine(dummyDate, shiftStart)
    end = datetime.combine(dummyDate, shiftEnd)

    slots = []
    while current < end:
        slots.append(current.time())
        current += timedelta(minutes=slotDuration)

    return slots