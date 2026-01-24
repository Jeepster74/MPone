import bcrypt

def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

# Initial user for testing
print(f"Hashed 'admin123': {hash_password('admin123')}")
