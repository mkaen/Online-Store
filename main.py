from datetime import datetime, timedelta

import requests
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_bootstrap import Bootstrap5
from flask_login import LoginManager, UserMixin, login_user, current_user, logout_user, login_required
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Integer, String, Float, ForeignKey
from sqlalchemy.orm import mapped_column, Mapped, DeclarativeBase, relationship
from werkzeug.security import generate_password_hash, check_password_hash
import os
from Exams.day_97_OnlineShop.forms import RegistrationForm
import stripe


stripe.api_key = os.environ.get('STRIPE_API_KEY')

app = Flask(__name__)

MY_DOMAIN = os.environ.get('MY_DOMAIN')


class Base(DeclarativeBase):
    pass


app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get('DATABASE')
db = SQLAlchemy(model_class=Base)
db.init_app(app)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
Bootstrap5(app)

# For Flash messages:
app.secret_key = os.environ.get('APP_SECRET_KEY')

login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)


# Many-to-many seose loomiseks kasutame assotsiatsioonitabelit.
cart = db.Table('cart',
                db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
                db.Column('product_id', db.Integer, db.ForeignKey('products.id'), primary_key=True)
                )


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    password: Mapped[str] = mapped_column(String(250), nullable=False)
    name: Mapped[str] = mapped_column(String(250), nullable=False)
    cart = relationship('Product', secondary=cart, backref='users')

    def add_to_cart(self, product):
        """Add product to cart."""
        if product not in self.cart:
            self.cart.append(product)
            db.session.commit()

    def remove_from_cart(self, product):
        """Remove product from cart."""
        if product in self.cart:
            self.cart.remove(product)
            db.session.commit()

    def clear_cart(self):
        """Clear cart."""
        self.cart.clear()
        db.session.commit()

    def get_cart_total(self):
        """Return total price of cart."""
        return round(sum(product.price for product in self.cart), 2)


class Product(db.Model):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    category: Mapped[str] = mapped_column(String(250), nullable=False)
    description: Mapped[str] = mapped_column(String(250), nullable=False)
    image: Mapped[str] = mapped_column(String(500), nullable=False)
    rate: Mapped[float] = mapped_column(Float)
    rate_count: Mapped[int] = mapped_column(Integer)

    # def check_image_url(url):
    #     """Check image url and return True if it exists and image file is correct and undamaged."""
    #     try:
    #         response = requests.get(url)
    #         if response.status_code == 200 and 'image' in response.headers['Content-Type']:
    #             return True
    #         else:
    #             return False
    #     except requests.exceptions.RequestException as e:
    #         print(f"Error checking URL: {e}")
    #         return False
    #
    #
    # endpoint = "https://fakestoreapi.com/products"
    # response = requests.get(endpoint)
    # all_products = response.json()
    # print(all_products)
    #
    #
    # for product in all_products:
    #     title = product['title']
    #     price = product['price']
    #     category = product['category']
    #     description = product['description']
    #     image = product['image']
    #     if not check_image_url(image):
    #         image = "https://upload.wikimedia.org/wikipedia/commons/1/14/No_Image_Available.jpg"
    #     rate = product['rating']['rate']
    #     rate_count = product['rating']['count']
    #     new_product = Product(title=title, price=price, category=category,
    #                           description=description, image=image, rate=rate, rate_count=rate_count)
    #     db.session.add(new_product)
    #     db.session.commit()


class Subscription(db.Model):
    __tablename__ = "subscriptions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(250), nullable=False, unique=True)


with app.app_context():
    db.create_all()

session = {
    "current_page": "home",
    "category_name": "",
    "product_id": ""
}
year = datetime.now().year
CATEGORIES = ["Men's Clothing", "Women's Clothing", "Jewelery", "Electronics"]


# @app.before_request
# def before_request():
#     session.permanent = True  # Sessiooni eluaeg on määratud konfis
#     session.modified = True   # Värskendame sessiooni iga päringuga
#     if current_user.is_authenticated:
#         now = datetime.utcnow()
#         last_activity = session.get('last_activity', now)
#         session['last_activity'] = now
#
#         # Kui kasutaja on olnud inaktiivne rohkem kui määratud aeg, logime ta välja
#         timeout = timedelta(minutes=15)  # Siin määrame timeouti aja (15 minutit)
#         if now - last_activity > timeout:
#             logout_user()
#             flash("You have been logged out due to inactivity.", "info")
#             return redirect(url_for('login'))


@app.route("/all_products")
def get_all_products():
    """Return all Product objects from database."""
    db_items = db.session.execute(db.select(Product))
    return db_items.scalars().all()


@app.route('/')
def home():
    session['current_page'] = "home"
    all_products = get_all_products()
    carousel_items = [item.image for item in all_products if item.rate >= 4.7]
    return render_template('index.html', year=year, products=all_products,
                           carousel_items=carousel_items, categories=CATEGORIES, current_user=current_user)


@app.route('/redirect_to_current')
def redirect_to_current():
    current_page = session.get('current_page')
    category_name = session.get('category_name')
    product_id = session.get('product_id')
    if current_page != "category" and current_page != "show_product":
        return redirect(url_for(current_page))
    if current_page == "category" and category_name:
        return redirect(url_for(current_page, category_name=category_name))
    if current_page == "show_product" and product_id:
        return redirect(url_for(current_page, product_id=product_id))
    else:
        flash('No current page set.')
        return redirect(url_for('home'))


@app.route('/category/<category_name>')
def category(category_name):
    session['current_page'] = "category"
    session["category_name"] = category_name
    all_products = get_all_products()
    category_products = [product for product in all_products if product.category.lower() == category_name.lower()]
    return render_template('category.html', year=year, category_products=category_products,
                           all_products=all_products, categories=CATEGORIES, category_name=category_name,
                           current_user=current_user)


@app.route('/show_product/<product_id>')
def show_product(product_id):
    session['current_page'] = "show_product"
    session['product_id'] = product_id
    product = db.get_or_404(Product, product_id)
    return render_template("product.html",
                           item=product,
                           year=year,
                           categories=CATEGORIES,
                           current_user=current_user)


@app.route('/add_to_basket/<product_id>')
def add_to_basket(product_id):
    if current_user.is_authenticated:
        product = db.get_or_404(Product, product_id)
        user = db.get_or_404(User, current_user.id)
        user.add_to_cart(product)
        flash('Product has been added to Your Cart.')
        return redirect_to_current()
    flash("To add item into cart, You must login first.")
    return redirect(url_for('login_page'))


@app.route('/remove_from_cart')
def remove_from_cart():
    product_id = request.args.get('product_id')
    product = db.get_or_404(Product, product_id)
    user = db.get_or_404(User, current_user.id)
    user.remove_from_cart(product)
    flash('Product has been removed from Your Cart.')
    return redirect_to_current()


@login_required
@app.route('/cart')
def cart():
    session['current_page'] = 'cart'
    if not current_user.is_authenticated:
        flash("You must be logged in to visit a cart page!")
        return redirect(url_for('login_page'))
    user = User.query.get(current_user.id)
    cart_items = user.cart
    total_sum = 0
    for item in cart_items:
        total_sum += item.price
    return render_template("cart.html", year=year,
                           current_user=current_user,
                           cart_items=cart_items,
                           total_sum=user.get_cart_total(),
                           categories=CATEGORIES)


@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = request.form.get('remember_me')
        user = db.session.execute(db.select(User).where(User.email == email)).scalar()
        if not user:
            flash('Invalid email. Please try again!')
            return redirect(url_for('login_page'))
        if not check_password_hash(user.password, password):
            flash('Incorrect password. Please try again!')
            return redirect(url_for('login_page'))
        else:
            login_user(user, remember=bool(remember))
            flash('Logged in successfully!')
            return redirect(url_for(session.get('current_page')))
    return render_template('login.html', year=year, current_user=current_user, categories=CATEGORIES)


@app.route('/register', methods=['GET', 'POST'])
def register_page():
    form = RegistrationForm()
    if form.validate_on_submit():
        email = form.email.data
        name = form.name.data
        existing_user = db.session.execute(db.select(User).where(User.email == email)).scalar()
        if existing_user:
            flash("You've already signed up with this email, log in instead!")
            return redirect(url_for('login_page'))
        hashed_and_salted_password = generate_password_hash(
            form.password.data,
            method='pbkdf2:sha256',
            salt_length=8
        )
        new_user = User(email=email, password=hashed_and_salted_password, name=name)
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user, remember=True)
        flash(f"Welcome {name.title()}! Your account has been created successfully! Happy shopping!")
        return redirect(url_for(session.get('current_page')))
    return render_template('register.html',
                           year=year,
                           form=form,
                           current_user=current_user,
                           categories=CATEGORIES)


@app.route('/log_out')
def log_out():
    logout_user()
    flash("You have been logged out!")
    return redirect(url_for('home'))


@app.route('/add_subscription', methods=['POST'])
def add_subscription():
    email = request.form.get('email').lower()
    result = db.session.execute(db.select(Subscription).where(Subscription.email == email))
    existing_subscription = result.scalars().all()
    if not existing_subscription:
        new_subscription = Subscription(email=email)
        db.session.add(new_subscription)
        db.session.commit()
        flash(f"Address {email} has been added to subscriptions list.")
        return redirect(url_for(session.get('current_page')))
    flash(f"Address {email} has already been subscribed.")
    return redirect(url_for(session.get('current_page')))


@app.route('/success')
def payment_success():
    user = db.get_or_404(User, current_user.id)
    user.clear_cart()
    return render_template('success.html')


@app.route('/cancel')
def payment_cancel():
    return render_template('cancel.html')


@login_required
@app.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    cart_items = current_user.cart
    line_items = []

    for product in cart_items:
        line_items.append({
            'price_data': {
                'currency': "eur",
                'product_data': {
                    'name': product.title,
                },
                'unit_amount': int(product.price * 100),  # Stripe nõuab summat sentides
            },
            'quantity': 1,
        })

    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=line_items,
            mode='payment',
            success_url=MY_DOMAIN + url_for('payment_success'),
            cancel_url=MY_DOMAIN + url_for('payment_cancel'),
        )
    except Exception as e:
        return str(e)

    return redirect(checkout_session.url, code=303)


if __name__ == '__main__':
    app.run(debug=True)
