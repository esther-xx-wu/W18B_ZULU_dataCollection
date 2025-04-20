import jwt as pyjwt

def validate_token(token):
    try:
        decoded = pyjwt.decode(token, options={"verify_signature": False})
        
        # Check if token has expired
        import time
        current_time = int(time.time())
        if decoded.get('exp') and decoded['exp'] < current_time:
            return False, "Token expired"
            
        return True, decoded
    except Exception as e:
        return False, str(e)