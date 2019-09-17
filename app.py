from flask import Flask, jsonify, request, render_template
from flask_restplus import Resource, Api, fields, reqparse
from flask_cors import CORS
from DB_Connection.db import init
from flask_jwt_extended import JWTManager
from Model.revokedTokenModel import revokedTokenModel
def factory():
    app = Flask(__name__)
    app.url_map.strict_slashes = False
    CORS(app)
    return app


app = factory()

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://admin:truong619@localhost/book'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
#app.config['SQLALCHEMY_ECHO'] = True
app.config['JWT_SECRET_KEY'] = 'jwt-secret-string'
app.config['JWT_BLACKLIST_ENABLED'] = True
app.config['JWT_BLACKLIST_TOKEN_CHECKS'] = ['access', 'refresh']

init(app)

jwt = JWTManager(app)

@app.route('/')
def helloworld():
    return "Hello"

@jwt.token_in_blacklist_loader
def check_if_token_in_blacklist(decrypted_token):
    jti = decrypted_token['jti']
    return revokedTokenModel.is_jti_blacklisted(jti)

api = Api(app, version='1.0', title='BookRental API',
          description='BookRental API'
          )

ns = api.namespace('api', description='BookRental API')

from DB_Connection.db import sql_db

db = sql_db()
@app.before_first_request
def create_tables():
    db.create_all()

from Resource import validatedResource
ns.add_resource(validatedResource.UserRegistration, '/registration')
ns.add_resource(validatedResource.UserLogin, '/login')
ns.add_resource(validatedResource.UserLogoutAccess, '/logout/access')
ns.add_resource(validatedResource.UserLogoutRefresh, '/logout/refresh')
ns.add_resource(validatedResource.TokenRefresh, '/token/refresh')
ns.add_resource(validatedResource.AllUsers, '/users')
ns.add_resource(validatedResource.SecretResource, '/secret')

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=False)
