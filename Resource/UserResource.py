from flask_jwt_extended import (jwt_required, get_jwt_identity)
from flask_restplus import Namespace, Resource, reqparse
from Model.models import *
from Utils import AuthorizationDoc
from Utils.InputValidation import *
from Utils.ES_Connection import *
import datetime
import html


api = Namespace('user')


profile_req = reqparse.RequestParser()
profile_req.add_argument('Authorization', type=str, location='headers', help='Bearer Access Token', required=True)


class UserProfile(Resource):
    @jwt_required
    @api.expect(profile_req)
    @api.doc(security='Bearer Auth', authorizations=AuthorizationDoc.authorizations)
    def get(self):
        current_user = get_jwt_identity()
        user_details = UserDetails.find_by_id(current_user[1])
        return {'data': user_details.as_dict()}, 200


update_profile_req = reqparse.RequestParser()
update_profile_req.add_argument('Authorization', type=str, location='headers', help='Bearer Access Token', required=True)
update_profile_req.add_argument('first_name', type=str, default='')
update_profile_req.add_argument('last_name', type=str, default='')
update_profile_req.add_argument('new_password', type=str, default='')
update_profile_req.add_argument('old_password', type=str, default='')


class UserUpdateProfile(Resource):
    @jwt_required
    @api.expect(update_profile_req)
    @api.doc(security='Bearer Auth', authorizations=AuthorizationDoc.authorizations)
    def post(self):
        data = update_profile_req. parse_args()
        current_user = get_jwt_identity()

        user_details = UserDetails.find_by_id(current_user[1])
        if 0 < len(data['new_password']) < 5:
            return 'Password is too short', 400
        if not user_details.verify_hash(data['old_password'], user_details.password):
            return 'Wrong password', 400
        if len(data['first_name']) > 0:
            user_details.first_name = data['first_name']
        if len(data['last_name']) > 0:
            user_details.last_name = data['last_name']
        if len(data['new_password']) > 0:
            user_details.password = user_details.generate_hash(data['new_password'])
        user_details.save_to_db()
        return 'success', 200


rating_get_req = reqparse.RequestParser()
rating_get_req.add_argument('Authorization', type=str, location='headers', help='Bearer Access Token', required=True)
rating_get_req.add_argument('book_id', type=str, required=True)

rating_post_req = reqparse.RequestParser()
rating_post_req.add_argument('Authorization', type=str, location='headers', help='Bearer Access Token', required=True)
rating_post_req.add_argument('book_id', type=str, required=True)
rating_post_req.add_argument('rating_num', type=int, required=True)
rating_post_req.add_argument('rating_comment', type=str, default='')


class UserRate(Resource):
    @jwt_required
    @api.expect(rating_get_req)
    def get(self):
        data = rating_get_req.parse_args()
        current_user = get_jwt_identity()
        v = validate_book_id(data['book_id'])
        if not v[0]:
            return {'message': 'Book does not exsit!'}, 400
        book_details = v[1]
        rating_details = RatingDetails.find_existing(current_user[1], book_details.ISBN)
        if not rating_details:
            return {
                'data': {
                    'rating_num': 0,
                    'rating_comment': ''
                 }
            }, 200
        return {'data': rating_details.as_dict()}, 200

    @jwt_required
    @api.expect(rating_post_req)
    @api.doc(security='Bearer Auth', authorizations=AuthorizationDoc.authorizations)
    def post(self):
        data = rating_post_req.parse_args()
        data['rating_comment'] = html.escape(data['rating_comment'])
        current_user = get_jwt_identity()
        # if not current_user:
        #     return {'message': 'You need login to rate this book', 'status': 'error'}, 401

        v = validate_book_id(data['book_id'])
        if not v[0]:
            return {'message': 'Book does not exsit!'}, 400

        if not 1 <= int(data['rating_num']) <= 5:
            return {'message': 'Rating num must be between 1 or 5'}, 400

        book_details = v[1]
        rating_details = RatingDetails.find_existing(current_user[1], book_details.ISBN)
        if not rating_details:
            rating_details = RatingDetails(book_id=data['book_id'],
                                           user_id=current_user[1],
                                           rating_num=data['rating_num'],
                                           rating_comment=data['rating_comment'])
            book_details.add_rating(data['rating_num'])
        else:
            if rating_details.rating_num != data['rating_num']:
                book_details.swap_rating(rating_details.rating_num, data['rating_num'])
            rating_details.rating_num = data['rating_num']
            rating_details.rating_comment = data['rating_comment']
        rating_details.save_to_db()
        book_details.save_to_db()
        update_ratings_book(book_details.ISBN, book_details.get_average_rating())
        return {'message': 'success'}, 200


lend_req = reqparse.RequestParser()
lend_req.add_argument('Authorization', type=str, location='headers', help='Bearer Access Token', required=True)
lend_req.add_argument('book_id', type=str, required=True)
lend_req.add_argument('price', type=int, required=True)
lend_req.add_argument('address', type=str, required=True)


class UserLend(Resource):
    @jwt_required
    @api.expect(lend_req)
    @api.doc(security='Bearer Auth', authorizations=AuthorizationDoc.authorizations)
    def post(self):
        data = lend_req.parse_args()
        data['address'] = html.escape(data['address'])
        current_user = get_jwt_identity()
        # user_details = UserDetails.find_by_email(current_user)
        # if not user_details:
        #     return {'message': 'Email does not exist'}, 401

        v = validate_book_id(data['book_id'])
        if not v[0]:
            return {'message': v[1]}, 400
        book_details = v[1]
        if data['price'] < 0:
            return {'message': 'price must be non-negative integer'}, 400

        day_upload = datetime.datetime.now()
        book_warehouse = BookWarehouse(book_id=data['book_id'],
                                       owner_id=current_user[1],
                                       price=data['price'],
                                       time_upload=day_upload,
                                       address=data['address'],
                                       borrowed_times=0,
                                       is_validate=1,
                                       validator=1,
                                       status=1)
        book_details.cnt_available += 1
        book_warehouse.save_to_db()
        book_details.save_to_db()
        update_lenders_book(book_details.ISBN, book_details.cnt_available)
        return {'message': 'success'}, 200


borrow_req = reqparse.RequestParser()
borrow_req.add_argument('Authorization', type=str, location='headers', help='Bearer Access Token', required=True)
borrow_req.add_argument('warehouse_id_list', type=validate_warehouse_id_list, required=True, location="json",
                        help='{"warehouse_id_list": [{"warehouse_id": "", "num_days_borrow": ""}, ]}')
borrow_req.add_argument("address", type=str, required=True)
borrow_req.add_argument("phone", type=validate_phone_number, help='+840123456789', required=True)
borrow_req.add_argument("payment_type", type=str, required=True, choices=("cash", "paypal"), default='cash')


class UserBorrow(Resource):
    @jwt_required
    @api.expect(borrow_req)
    @api.doc(security='Bearer Auth', authorizations=AuthorizationDoc.authorizations)
    def post(self):
        data = borrow_req.parse_args()
        data['address'] = html.escape(data['address'])
        current_user = get_jwt_identity()

        # user_details = UserDetails.find_by_email(current_user)
        # if not user_details:
        #     return {'message': 'Email does not exist'}, 401
        res = dict()
        res['data'] = []
        total_price = 0
        prev_id = -1
        for each_warehouse in data['warehouse_id_list']:
            if each_warehouse['warehouse_id'] == prev_id:
                res['data'].append({'warehouse_id': each_warehouse['warehouse_id'],
                                    'message': 'Duplicate warehouse id'})
                continue
            prev_id = each_warehouse['warehouse_id']
            warehouse_details = BookWarehouse.find_by_id(each_warehouse['warehouse_id'])
            if not warehouse_details:
                res['data'].append({'warehouse_id': each_warehouse['warehouse_id'],
                                    'message': 'Warehouse does not exist'})
                continue

            if warehouse_details.status != 1:
                res['data'].append({'warehouse_id': each_warehouse['warehouse_id'],
                                    'message': 'Book is not available'})
                continue

            if warehouse_details.owner_id == current_user[1]:
                res['data'].append({'warehouse_id': each_warehouse['warehouse_id'],
                                    'message': 'Can not borrow your own book'})
                continue
            total_price += warehouse_details.price * each_warehouse['num_days_borrow']

        user_details = UserDetails.find_by_id(current_user[1])
        if data['payment_type'] == 'cash':
            if user_details.cash < total_price:
                res['data'].append({'message': 'Not enough cash'})

        if len(res['data']):
            return res, 400

        day_borrow = datetime.datetime.now()
        for each_warehouse in data['warehouse_id_list']:
            warehouse_details = BookWarehouse.find_by_id(each_warehouse['warehouse_id'])
            book_details = BookDetails.find_by_isbn(warehouse_details.book_id)
            day_expected_return = day_borrow + datetime.timedelta(days=each_warehouse['num_days_borrow'])
            price = warehouse_details.price * each_warehouse['num_days_borrow']

            borrow_details = BorrowDetails(warehouse_id=each_warehouse['warehouse_id'],
                                           borrower_id=current_user[1],
                                           day_borrow=day_borrow,
                                           day_expected_return=day_expected_return,
                                           address=data['address'],
                                           phone=data['phone'],
                                           price=price,
                                           payment_type=data['payment_type'],
                                           status=0)
            warehouse_details.status = 0
            warehouse_details.borrowed_times += 1
            if data['payment_type'] == 'cash':
                user_details.cash -= price
            user_details.outcome += price
            owner_details = UserDetails.find_by_id(warehouse_details.owner_id)
            owner_details.cash += price
            owner_details.income += price
            book_details.cnt_available -= 1

            user_details.save_to_db()
            owner_details.save_to_db()
            borrow_details.save_to_db()
            warehouse_details.save_to_db()
            book_details.save_to_db()
            update_lenders_book(book_details.ISBN, book_details.cnt_available)
        return {'message': 'success'}, 200


return_req = reqparse.RequestParser()
return_req.add_argument('Authorization', type=str, location='headers', help='Bearer Access Token', required=True)
return_req.add_argument('borrow_id', type=int, required=True)
return_req.add_argument('address', type=str, required=True)


class UserReturn(Resource):
    @jwt_required
    @api.expect(return_req)
    @api.doc(security='Bearer Auth', authorizations=AuthorizationDoc.authorizations)
    def post(self):
        data = return_req.parse_args()
        data['address'] = html.escape(data['address'])
        current_user = get_jwt_identity()
        borrow_details = BorrowDetails.find_by_id(data['borrow_id'])
        if not borrow_details:
            return {'message': 'Invalid borrow id'}, 400
        elif borrow_details.borrower_id != current_user[1] or borrow_details.status != 0:
            return {'message': 'Invalid borrow id'}, 400
        warehouse_details = BookWarehouse.find_by_id(borrow_details.warehouse_id)
        if not warehouse_details:
            return {'message': 'Invalid borrow id'}, 400

        book_details = BookDetails.find_by_isbn(warehouse_details.book_id)
        warehouse_details.status = 1
        borrow_details.status = 1
        borrow_details.day_actual_return = datetime.datetime.now()
        book_details.cnt_available += 1

        warehouse_details.save_to_db()
        borrow_details.save_to_db()
        book_details.save_to_db()
        update_lenders_book(book_details.ISBN, book_details.cnt_available)
        return {'message': 'success'}, 200


lendings_req = reqparse.RequestParser()
lendings_req.add_argument('Authorization', type=str, location='headers', help='Bearer Access Token', required=True)
lendings_req.add_argument('limit', type=int, default=5)
lendings_req.add_argument('page', type=int, default=1)


class UserLendings(Resource):
    @jwt_required
    @api.expect(lendings_req)
    @api.doc(security='Bearer Auth', authorizations=AuthorizationDoc.authorizations)
    def get(self):
        data = lendings_req.parse_args()
        current_user = get_jwt_identity()
        res = dict()
        res['data'] = []
        warehouses_detail = BookWarehouse.find_by_owner(current_user[1], data['limit'], data['page'])
        for each_warehouse in warehouses_detail['data']:
            each_res = dict()
            book = BookDetails.find_by_isbn(each_warehouse['book_id'])
            author = AuthorDetails.find_by_id(book.author_id)
            each_res['book_title'] = book.book_title
            each_res['book_cover'] = book.book_cover
            each_res['author'] = author.author_name
            each_res['warehouse_id'] = each_warehouse['warehouse_id']
            each_res['book_id'] = each_warehouse['book_id']
            each_res['price'] = each_warehouse['price']
            each_res['time_upload'] = each_warehouse['time_upload']
            each_res['borrowed_times'] = each_warehouse['borrowed_times']
            each_res['status'] = each_warehouse['status']
            each_res['is_validate'] = each_warehouse['is_validate']
            res['data'].append(each_res)
        return res, 200


borrowings_req = reqparse.RequestParser()
borrowings_req.add_argument('Authorization', type=str, location='headers', help='Bearer Access Token', required=True)
borrowings_req.add_argument('limit', type=int, default=5)
borrowings_req.add_argument('page', type=int, default=1)


class UserBorrowings(Resource):
    @jwt_required
    @api.expect(borrowings_req)
    @api.doc(security='Bearer Auth', authorizations=AuthorizationDoc.authorizations)
    def get(self):
        data = borrowings_req.parse_args()
        current_user = get_jwt_identity()
        res = dict()
        res['data'] = []
        borrowings_detail = BorrowDetails.find_borrowings_by_borrower(current_user[1], data['limit'], data['page'])
        for each_borrowing in borrowings_detail['data']:
            each_res = dict()
            warehouse = BookWarehouse.find_by_id(each_borrowing['warehouse_id'])
            book = BookDetails.find_by_isbn(warehouse.book_id)
            author = AuthorDetails.find_by_id(book.author_id)
            owner = UserDetails.find_by_id(warehouse.owner_id)
            each_res['borrow_id'] = each_borrowing['borrow_id']
            each_res['day_borrow'] = each_borrowing['day_borrow']
            each_res['day_expected_return'] = each_borrowing['day_expected_return']
            each_res['phone'] = each_borrowing['phone']
            each_res['address'] = each_borrowing['address']
            each_res['price'] = each_borrowing['price']
            each_res['payment_type'] = each_borrowing['payment_type']
            each_res['book_title'] = book.book_title
            each_res['book_cover'] = book.book_cover
            each_res['author'] = author.author_name
            each_res['owner'] = owner.email
            each_res['warehouse_id'] = warehouse.warehouse_id
            res['data'].append(each_res)
        return res, 200


ratings_req = reqparse.RequestParser()
ratings_req.add_argument('Authorization', type=str, location='headers', help='Bearer Access Token', required=True)
ratings_req.add_argument('limit', type=int, default=5)
ratings_req.add_argument('page', type=int, default=1)


class UserRatings(Resource):
    @jwt_required
    @api.expect(ratings_req)
    @api.doc(security='Bearer Auth', authorizations=AuthorizationDoc.authorizations)
    def get(self):
        data = ratings_req.parse_args()
        current_user = get_jwt_identity()
        return RatingDetails.find_by_user(current_user[1], data['limit'], data['page'])


ratings_stat_req = reqparse.RequestParser()
ratings_stat_req.add_argument('Authorization', type=str, location='headers', help='Bearer Access Token', required=True)


class UserRatingsStat(Resource):
    @jwt_required
    @api.expect(ratings_stat_req)
    @api.doc(security='Bearer Auth', authorizations=AuthorizationDoc.authorizations)
    def get(self):
        data = ratings_req.parse_args()
        current_user = get_jwt_identity()
        return {'data': [
            {str(i): RatingDetails.find_by_user_and_rating_num(current_user[1], i)} for i in range(1, 6)
        ]}, 200


transactions_req = reqparse.RequestParser()
transactions_req.add_argument('Authorization', type=str, location='headers', help='Bearer Access Token', required=True)
transactions_req.add_argument('mode', type=str, choices=('income', 'outcome'), default="outcome", required=True)
transactions_req.add_argument('limit', type=int, default=5)
transactions_req.add_argument('page', type=int, default=1)


class UserTransactions(Resource):
    @jwt_required
    @api.expect(transactions_req)
    @api.doc(security='Bearer Auth', authorizations=AuthorizationDoc.authorizations)
    def get(self):
        data = transactions_req.parse_args()
        current_user = get_jwt_identity()

        res = dict()
        res['data'] = dict()
        user_details = UserDetails.find_by_id(current_user[1])

        if data['mode'] == 'outcome':
            res['data']['total'] = user_details.outcome
            res['data']['details'] = []
            borrow_details = BorrowDetails.find_by_borrower(current_user[1], data['limit'], data['page'])
            for each_borrow in borrow_details:
                res['data']['details'].append({
                    'ISBN': each_borrow.book_warehouse.book_details.ISBN,
                    'book_title': each_borrow.book_warehouse.book_details.book_title,
                    'book_cover': each_borrow.book_warehouse.book_details.book_cover,
                    'author': each_borrow.book_warehouse.book_details.author_details.author_name,
                    'day_borrow': str(each_borrow.day_borrow),
                    'day_expected_return': str(each_borrow.day_expected_return),
                    'day_actual_return': str(each_borrow.day_actual_return),
                    'phone': each_borrow.phone,
                    'address': each_borrow.address,
                    'price': each_borrow.price,
                    'payment_type': each_borrow.payment_type,
                    'status': each_borrow.status
                })
            return res, 200
        elif data['mode'] == 'income':
            res['data']['total'] = user_details.income
            res['data']['details'] = []
            borrow_details = BorrowDetails.find_by_owner(current_user[1], data['limit'], data['page'])
            for each_borrow in borrow_details:
                borrower_details = UserDetails.find_by_id(each_borrow.borrower_id)
                res['data']['details'].append({
                    'ISBN': each_borrow.book_warehouse.book_details.ISBN,
                    'book_title': each_borrow.book_warehouse.book_details.book_title,
                    'book_cover': each_borrow.book_warehouse.book_details.book_cover,
                    'author': each_borrow.book_warehouse.book_details.author_details.author_name,
                    'borrower_email': borrower_details.email,
                    'day_borrow': str(each_borrow.day_borrow),
                    'day_expected_return': str(each_borrow.day_expected_return),
                    'day_actual_return': str(each_borrow.day_actual_return),
                    'phone': each_borrow.phone,
                    'address': each_borrow.address,
                    'price': each_borrow.price,
                    'status': each_borrow.status
                })
            return res, 200


remove_warehouse_req = reqparse.RequestParser()
remove_warehouse_req.add_argument('Authorization', type=str, location='headers', help='Bearer Access Token', required=True)
remove_warehouse_req.add_argument('warehouse_id', type=int, required=True)


class UserRemoveWarehouse(Resource):
    @jwt_required
    @api.expect(remove_warehouse_req)
    @api.doc(security='Bearer Auth', authorizations=AuthorizationDoc.authorizations)
    def post(self):
        data = remove_warehouse_req.parse_args()
        current_user = get_jwt_identity()
        warehouse_details = BookWarehouse.find_by_id(data['warehouse_id'])
        if not warehouse_details.owner_id == current_user[1]:
            return {'message': 'This book does not belong to you'}, 400
        if warehouse_details.status == 0:
            return {'message': 'This book has been borrowed'}, 400
        if warehouse_details.status == 2:
            return {'message': 'This book had been removed'}, 400
        if warehouse_details.status == 1:
            warehouse_details.status = 2
            warehouse_details.save_to_db()

        return {'message': 'success'}, 200


