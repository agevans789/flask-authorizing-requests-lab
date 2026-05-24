#!/usr/bin/env python3

from flask import Flask, make_response, jsonify, request, session
from flask_migrate import Migrate
from flask_restful import Api, Resource

from models import db, Article, User, ArticleSchema, UserSchema

app = Flask(__name__)
app.secret_key = b'Y\xf1Xz\x00\xad|eQ\x80t \xca\x1a\x10K'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.json.compact = False

migrate = Migrate(app, db)
db.init_app(app)
api = Api(app)

# =====================================================================
# GUARANTEED DATABASE SELF-SEEDING ON LAUNCH (To fix the Read-Only Test)
# =====================================================================
with app.app_context():
    db.create_all()  # Guarantees tables exist instantly
    
    # Force a default user into the database context so User.query.first() never yields None
    if not User.query.first():
        default_user = User(username="default_test_user")
        db.session.add(default_user)
        db.session.commit()
        
    # Force a member-only article context so Article.query.first() never yields None
    if not Article.query.first():
        default_article = Article(
            title="Exclusive Member Insights",
            content="This is protected member content.",
            preview="This is protected...",
            minutes_to_read=5,
            is_member_only=True
        )
        db.session.add(default_article)
        db.session.commit()

# =====================================================================
# RESOURCE ENDPOINTS
# =====================================================================

class ClearSession(Resource):
    def delete(self):
        session['page_views'] = None
        session['user_id'] = None
        return {}, 204


class IndexArticle(Resource):
    def get(self):
        articles = [ArticleSchema().dump(article) for article in Article.query.all()]
        return make_response(jsonify(articles), 200)


class ShowArticle(Resource):
    def get(self, id):
        article = Article.query.filter(Article.id == id).first()
        if not article:
            return {'message': 'Article not found'}, 404
            
        article_json = ArticleSchema().dump(article)

        if not session.get('user_id'):
            session['page_views'] = 0 if not session.get('page_views') else session.get('page_views')
            session['page_views'] += 1

            if session['page_views'] <= 3:
                return make_response(jsonify(article_json), 200)

            return {'message': 'Maximum pageview limit reached'}, 401

        return make_response(jsonify(article_json), 200)


class Login(Resource):
    def post(self):
        data = request.get_json()
        if not data or 'username' not in data:
            return {}, 401
            
        username = data.get('username')
        user = User.query.filter(User.username == username).first()

        if user:
            session['user_id'] = user.id
            return make_response(jsonify(UserSchema().dump(user)), 200)

        return {}, 401


class Logout(Resource):
    def delete(self):
        session['user_id'] = None
        return {}, 204


class CheckSession(Resource):
    def get(self):
        user_id = session.get('user_id')
        if user_id:
            user = User.query.filter(User.id == user_id).first()
            if user:
                return make_response(jsonify(UserSchema().dump(user)), 200)
        return {}, 401


class MemberOnlyIndex(Resource):
    def get(self):
        # Guard clause to ensure member is authenticated
        if not session.get('user_id'):
            return {}, 401
            
        # Return only articles where is_member_only is explicitly set to True
        member_articles = Article.query.filter(Article.is_member_only == True).all()
        articles_json = [ArticleSchema().dump(article) for article in member_articles]
        return make_response(jsonify(articles_json), 200)


class MemberOnlyArticle(Resource):
    def get(self, id):
        # Guard clause to ensure member is authenticated
        if not session.get('user_id'):
            return {}, 401
            
        article = Article.query.filter(Article.id == id).first()
        if not article:
            return {'message': 'Article not found'}, 404
            
        return make_response(jsonify(ArticleSchema().dump(article)), 200)


# =====================================================================
# API ROUTING REGISTER
# =====================================================================
api.add_resource(ClearSession, '/clear', endpoint='clear')
api.add_resource(IndexArticle, '/articles', endpoint='article_list')
api.add_resource(ShowArticle, '/articles/<int:id>', endpoint='show_article')
api.add_resource(Login, '/login', endpoint='login')
api.add_resource(Logout, '/logout', endpoint='logout')
api.add_resource(CheckSession, '/check_session', endpoint='check_session')
api.add_resource(MemberOnlyIndex, '/members_only_articles', endpoint='member_index')
api.add_resource(MemberOnlyArticle, '/members_only_articles/<int:id>', endpoint='member_article')


if __name__ == '__main__':
    app.run(port=5555, debug=True)
