from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import mysql.connector
from typing import Optional

app = FastAPI(title="Smart Parking 'DEMO' API", version="1.0")

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="smart_parking"
    )

class SlotUpdate(BaseModel):
    status: str
    warna: Optional[str] = "-"
    plat: Optional[str] = "-"

@app.get("/api/parking")
def get_parking_status():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM parking_slots")
        result = cursor.fetchall()
        cursor.close()
        conn.close()
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/parking/{slot_name}")
def update_parking_slot(slot_name: str, data: SlotUpdate):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = """
            UPDATE parking_slots 
            SET status = %s, warna = %s, plat = %s 
            WHERE slot_name = %s
        """
        cursor.execute(query, (data.status, data.warna, data.plat, slot_name))
        conn.commit()
        
        rows_affected = cursor.rowcount
        cursor.close()
        conn.close()
        
        if rows_affected == 0:
            raise HTTPException(status_code=404, detail=f"Slot {slot_name} tidak ditemukan di database!")
            
        return {
            "success": True,
            "message": f"Slot {slot_name} berhasil di-update!",
            "updated_data": data.dict()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)