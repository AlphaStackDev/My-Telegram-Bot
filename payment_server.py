from fastapi import FastAPI, Request, HTTPException
import asyncpg
import uvicorn

app = FastAPI()

# Database config (Ensure it matches Alpha_PBot.py)
DB_CONFIG = {
    "host": "localhost",
    "user": "postgres",
    "password": "your_new_password",
    "database": "unical_bot"
}

@app.post("/webhook/moniepoint")
async def handle_moniepoint_webhook(request: Request):
    data = await request.json()
    
    # Verify the event (Moniepoint typically sends 'charge.success')
    event = data.get("event")
    if event == "charge.success":
        # Extract the reg_number from the metadata or customer reference
        # Adjust 'customer_reference' based on what you send to Moniepoint
        reg_number = data.get("data", {}).get("customerReference")
        
        # Update database
        conn = await asyncpg.connect(**DB_CONFIG)
        try:
            await conn.execute(
                "UPDATE students SET has_paid = TRUE WHERE reg_number = $1",
                reg_number
            )
        finally:
            await conn.close()
            
        return {"status": "success"}
    
    return {"status": "ignored"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)