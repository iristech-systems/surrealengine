"""Test script for new SurrealEngine features.

This script demonstrates the use of the new features added to SurrealEngine:
1. Field-level indexing with the `index_with` parameter
2. Aggregation pipelines for complex data transformations
3. New field types (EmailField, URLField, DictField, etc.)
4. Pagination functionality
"""

import asyncio
import datetime
from surrealengine import (
    Document, create_connection,
    StringField, IntField, FloatField, DateTimeField, EmailField, URLField, DictField,
    IPAddressField, SlugField, ChoiceField, SetField, ReferenceField,
    Count, Mean, Sum, Min, Max, Median, StdDev, Variance, Percentile, Distinct, GroupConcat
)
from surrealengine.logging import logger

# Set up logging
logger.set_level(10)  # DEBUG level

# Define document classes with the new field types and field-level indexing
class User(Document):
    name = StringField(required=True, indexed=True)
    email = EmailField(required=True, indexed=True, unique=True)
    website = URLField()
    settings = DictField()
    ip_address = IPAddressField(ipv4_only=True)
    username = SlugField(required=True, indexed=True, unique=True)
    status = ChoiceField(choices=['active', 'inactive', 'suspended'])
    country = StringField(indexed=True, index_with=["city"])  # Multi-field index
    city = StringField()
    age = IntField(indexed=True)

class Product(Document):
    """Product document with field-level indexing."""

    name = StringField(required=True, indexed=True)
    price = FloatField(required=True, indexed=True)
    category = StringField(required=True, indexed=True, index_with=["subcategory"])  # Multi-field index
    subcategory = StringField()
    status = StringField(default="active")
    tags = SetField(StringField())
    created_at = DateTimeField(default=datetime.datetime.now)

    class Meta:
        collection = "product"

class Order(Document):
    """Order document with field-level indexing."""

    user_id = ReferenceField(User, required=True, indexed=True)
    product_id = ReferenceField(Product, required=True, indexed=True)
    quantity = IntField(required=True)
    price = FloatField(required=True)
    status = StringField(default="pending")
    created_at = DateTimeField(default=datetime.datetime.now)

    class Meta:
        collection = "order"

async def main():
    # Connect to SurrealDB
    db = create_connection(
        url="ws://localhost:8001/rpc",
        namespace="test_ns",
        database="test_db",
        username="root",
        password="root",
        make_default=True,
        async_mode=True
    )
    await db.connect()

    try:
        # Create tables
        logger.info("Creating tables...")
        await User.create_table(schemafull=True)
        await Product.create_table(schemafull=True)
        await Order.create_table(schemafull=True)

        # Create indexes
        logger.info("Creating indexes...")
        await User.create_indexes()
        await Product.create_indexes()
        await Order.create_indexes()

        # Create users
        logger.info("Creating test users...")
        users = []
        for i in range(10):
            user = User(
                name=f"User {i}",
                email=f"user{i}@example.com",
                website=f"https://example.com/user{i}",
                settings=dict(theme="dark") if i % 3 == 0 else dict(theme="light"),
                ip_address=f"192.168.1.{i}",
                username=f"user-{i}",
                status='active' if i % 3 == 0 else ('inactive' if i % 3 == 1 else 'suspended'),
                country=['USA', 'Canada', 'UK', 'Australia', 'Germany'][i % 5],
                city=['New York', 'Toronto', 'London', 'Sydney', 'Berlin'][i % 5],
                age=25 + i
            )
            await user.save()
            users.append(user)
            logger.debug(f"Created user: {user.name}")

        # Create products
        logger.info("Creating products...")
        products = []
        for i in range(10):
            product = Product(
                name=f"Product {i}",
                price=10.0 * (i + 1),
                category=['Electronics', 'Clothing', 'Books', 'Home', 'Sports'][i % 5],
                subcategory=['Phones', 'Shirts', 'Fiction', 'Kitchen', 'Running'][i % 5],
                status='active' if i % 4 != 0 else 'discontinued',
                tags=[f"tag{i}", f"category-{i % 5}", "product"]
            )
            await product.save()
            products.append(product)
            logger.debug(f"Created product: {product.name}")

        # Create orders
        logger.info("Creating orders...")
        orders = []
        for i in range(20):
            user = users[i % len(users)]
            product = products[i % len(products)]
            order = Order(
                user_id=user,
                product_id=product,
                quantity=i % 3 + 1,
                price=product.price * (i % 3 + 1),
                status='completed' if i % 3 == 0 else ('pending' if i % 3 == 1 else 'cancelled')
            )
            await order.save()
            orders.append(order)
            logger.debug(f"Created order: {order.id}")

        # Test pagination
        logger.info("Testing pagination...")
        page1 = await User.objects.paginate(page=1, per_page=5)
        logger.info(f"Page 1: {len(page1.items)} items, total: {page1.total}, pages: {page1.pages}")
        for user in page1:
            logger.info(f"  - {user.name} ({user.email})")

        page2 = await User.objects.paginate(page=2, per_page=5)
        logger.info(f"Page 2: {len(page2.items)} items, has_next: {page2.has_next}, has_prev: {page2.has_prev}")
        for user in page2:
            logger.info(f"  - {user.name} ({user.email})")

        # Test filtering with new field types
        logger.info("Testing filtering with new field types...")
        active_users = await User.objects.filter(status='active').all()
        logger.info(f"Active users: {len(active_users)}")
        logger.info(f"Active user without settings: {active_users[0].to_dict()}")

        dark_theme_users = await User.objects.filter(settings__theme="dark").all()
        logger.info(f"Users with dark theme: {len(dark_theme_users)}")

        # Test aggregation pipeline
        logger.info("Testing aggregation pipeline...")

        # Group products by category and subcategory
        logger.info("Grouping products by category and subcategory...")
        product_stats = await Product.objects.aggregate() \
            .group(["category", "subcategory"], 
                   count=Count(), 
                   avg_price=Mean("price"), 
                   min_price=Min("price"),
                   max_price=Max("price")) \
            .sort(count="DESC") \
            .execute()

        logger.info("Product statistics:")
        for stat in product_stats:
            logger.info(f"Category: {stat.get('category')}, Subcategory: {stat.get('subcategory')}, "
                       f"Count: {stat.get('count')}, Avg Price: {stat.get('avg_price')}, "
                       f"Min Price: {stat.get('min_price')}, Max Price: {stat.get('max_price')}")

        # Group orders by status
        logger.info("Grouping orders by status...")
        order_stats = await Order.objects.aggregate() \
            .group("status", 
                   count=Count(), 
                   total_value=Sum("price"), 
                   avg_value=Mean("price"),
                   median_value=Median("price")) \
            .execute()

        logger.info("Order statistics:")
        for stat in order_stats:
            logger.info(f"Status: {stat.get('status')}, Count: {stat.get('count')}, "
                       f"Total Value: {stat.get('total_value')}, Avg Value: {stat.get('avg_value')}, "
                       f"Median Value: {stat.get('median_value')}")

        # Group users by country and city
        logger.info("Grouping users by country and city...")
        user_stats = await User.objects.aggregate() \
            .group(["country", "city"], 
                   count=Count(), 
                   avg_age=Mean("age"), 
                   min_age=Min("age"),
                   max_age=Max("age"),
                   stddev_age=StdDev("age")) \
            .execute()

        logger.info("User statistics:")
        for stat in user_stats:
            logger.info(f"Country: {stat.get('country')}, City: {stat.get('city')}, "
                       f"Count: {stat.get('count')}, Avg Age: {stat.get('avg_age')}, "
                       f"Min Age: {stat.get('min_age')}, Max Age: {stat.get('max_age')}, "
                       f"StdDev Age: {stat.get('stddev_age')}")

        # Project specific fields
        logger.info("Projecting specific fields...")
        user_projections = await User.objects.aggregate() \
            .project(
                name=True,
                email=True,
                location=f"string::concat(city, ', ', country)",
                is_adult="age >= 18"
            ) \
            .execute()

        logger.info("User projections:")
        for projection in user_projections:
            logger.info(f"Name: {projection.get('name')}, Email: {projection.get('email')}, "
                       f"Location: {projection.get('location')}, Is Adult: {projection.get('is_adult')}")

        # Clean up
        logger.info("Cleaning up...")
        for order in orders:
            await order.delete()
        for product in products:
            await product.delete()
        for user in users:
            await user.delete()

        logger.info("Test completed successfully!")

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        raise

    finally:
        # Close the connection
        await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
