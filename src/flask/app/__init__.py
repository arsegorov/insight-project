from flask import Flask
app = Flask(__name__)  # Keep this line above ``from app import views``, or else!

from app import views
