"""E-commerce application entry point with sample usage."""

from .models import Address, Customer, Discount, PaymentMethod, Product
from .services import (
    AnalyticsService,
    OrderService,
    PaymentProcessor,
    ProductCatalog,
    ShoppingCart,
)


def setup_catalog() -> ProductCatalog:
    catalog = ProductCatalog()
    products = [
        Product(1, "Laptop Pro 15", 4999.99, stock=50, category="electronics",
                description="High-performance laptop with 32GB RAM"),
        Product(2, "Wireless Mouse", 129.99, stock=200, category="accessories",
                description="Ergonomic wireless mouse with USB-C"),
        Product(3, "USB-C Hub", 199.99, stock=100, category="accessories",
                description="7-in-1 USB-C hub with HDMI"),
        Product(4, "Monitor 27\"", 1899.99, stock=30, category="electronics",
                description="4K IPS monitor with HDR"),
        Product(5, "Keyboard Mech", 349.99, stock=150, category="accessories",
                description="Mechanical keyboard with RGB"),
        Product(6, "Webcam HD", 249.99, stock=80, category="electronics",
                description="1080p webcam with autofocus"),
        Product(7, "Headphones BT", 599.99, stock=120, category="audio",
                description="Noise-cancelling Bluetooth headphones"),
        Product(8, "Desk Lamp LED", 89.99, stock=300, category="office",
                description="Adjustable LED desk lamp"),
    ]
    for p in products:
        catalog.add_product(p)
    return catalog


def create_sample_customer() -> Customer:
    customer = Customer(
        id=1,
        name="Jan Kowalski",
        email="jan@example.com",
    )
    customer.add_address(
        Address(street="ul. Marszałkowska 1", city="Warszawa", zip_code="00-001")
    )
    return customer


def run_sample_workflow():
    catalog = setup_catalog()
    payment = PaymentProcessor()
    order_service = OrderService(catalog, payment)
    analytics = AnalyticsService(order_service)

    customer = create_sample_customer()
    cart = ShoppingCart(customer)

    # Add items
    cart.add_item(catalog.get_product(1), 1)  # Laptop
    cart.add_item(catalog.get_product(2), 2)  # 2x Mouse
    cart.add_item(catalog.get_product(5), 1)  # Keyboard

    # Apply discount
    discount = Discount(code="WELCOME10", percentage=10, min_order=100)
    cart.apply_discount(discount)

    # Create order
    order, msg = order_service.create_order(
        cart=cart,
        shipping_address=customer.primary_address(),
        payment_method=PaymentMethod.CREDIT_CARD,
        payment_details={"card_number": "4111111111111111", "cvv": "123"},
    )

    if order:
        print(f"Order #{order.id}: {order.status.value}, total={order.total:.2f}")

    # Analytics
    summary = analytics.revenue_summary()
    print(f"Revenue: {summary['total_revenue']:.2f}")

    return order


if __name__ == "__main__":
    run_sample_workflow()
