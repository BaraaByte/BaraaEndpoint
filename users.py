from werkzeug.security import generate_password_hash

# change username/password here
USERS = {
    "admin": generate_password_hash("Ma3ruag3")
}
