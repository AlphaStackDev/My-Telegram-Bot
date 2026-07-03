from fastapi import FastAPI, Request, HTTPException
import hmac
import hashlib
import json
import asyncpg


app = FastAPI()
SECRET_KEY = "YOUR_PAYSTACK_SECRET_KEY" # Found in your Paystack dashboard
DB_CONFIG = {'host': 'localhost', 'user': 'root', 'password': 'your_password', 'db': 'unical_bot'}

@app.post("/webhook")
async def paystack_webhook(request: Request):
    payload = await request.body()
    signature = request.headers.get('x-paystack-signature')

    # 1. Verify the signature to ensure it's from Paystack
    hash = hmac.new(SECRET_KEY.encode(), payload, hashlib.sha512).hexdigest()
    if hash != signature:
        raise HTTPException(status_code=400, detail="Invalid signature")

    event = json.loads(payload)
    
    # 2. Check if payment was successful
    if event['event'] == 'charge.success':
        customer_email = event['data']['customer']['email']
        
        # 3. Update the student's download count in DB
        conn = await asyncpg.connect(**DB_CONFIG)
        try:
            # Reset downloads (e.g., set to 0 or add a credit pack)
            await conn.execute(
                "UPDATE students SET download_count = 0 WHERE email = $1",
                customer_email,
            )
        finally:
            await conn.close()

        
    return {"status": "success"}