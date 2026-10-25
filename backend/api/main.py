from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import mysql.connector
from typing import Optional
import os
from dotenv import load_dotenv

# Load file .env
load_dotenv()
app = FastAPI(title="Smart Parking 'DEMO' API", version="1.0")

DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")

def get_db_connection():
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
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

@app.get("/api/parking/plate/{plat_query}")
def get_parking_by_plate(plat_query: str):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Pakai LIKE supaya pencarian fleksibel (bisa cari sebagian plat)
        query = "SELECT * FROM parking_slots WHERE plat LIKE %s"
        cursor.execute(query, (f"%{plat_query}%",))
        result = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        if not result:
            return {
                "success": False, 
                "message": f"Kendaraan dengan plat '{plat_query}' tidak ditemukan di slot manapun."
            }
            
        return {
            "success": True,
            "data": result
        }
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
    port = os.getenv("PORT")
    uvicorn.run("main:app", host="127.0.0.1", port=port, reload=True)