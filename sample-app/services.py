"""Business logic services for e-commerce application."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

from .models import (
    Address,
    CartItem,
    Customer,
    Discount,
    Order,
    OrderStatus,
    PaymentMethod,
    Product,
)

logger = logging.getLogger(__name__)


class ProductCatalog:
    """Manages product inventory and search."""

    def __init__(self) -> None:
        self._products: Dict[int, Product] = {}

    def add_product(self, product: Product) -> None:
        self._products[product.id] = product

    def get_product(self, product_id: int) -> Optional[Product]:
        return self._products.get(product_id)

    def search(self, query: str, category: str = "") -> List[Product]:
        results = []
        query_lower = query.lower()
        for p in self._products.values():
            if query_lower in p.name.lower() or query_lower in p.description.lower():
                if not category or p.category == category:
                    results.append(p)
        return results

    def low_stock_products(self, threshold: int = 5) -> List[Product]:
        return [p for p in self._products.values() if 0 < p.stock <= threshold]

    def restock(self, product_id: int, quantity: int) -> bool:
        product = self.get_product(product_id)
        if product is None:
            return False
        product.stock += quantity
        logger.info(f"Restocked product {product_id}: +{quantity} (now {product.stock})")
        return True


class ShoppingCart:
    """Shopping cart with validation and discount support."""

    def __init__(self, customer: Customer) -> None:
        self.customer = customer
        self._items: Dict[int, CartItem] = {}
        self._discount: Optional[Discount] = None

    def add_item(self, product: Product, quantity: int = 1) -> Tuple[bool, str]:
        if not product.is_available():
            return False, f"Product {product.name} is out of stock"
        if quantity > product.stock:
            return False, f"Only {product.stock} units available"

        if product.id in self._items:
            self._items[product.id].quantity += quantity
        else:
            self._items[product.id] = CartItem(product=product, quantity=quantity)

        logger.info(f"Added {quantity}x {product.name} to cart for {self.customer.name}")
        return True, "OK"

    def remove_item(self, product_id: int) -> bool:
        if product_id in self._items:
            del self._items[product_id]
            return True
        return False

    def update_quantity(self, product_id: int, quantity: int) -> Tuple[bool, str]:
        if product_id not in self._items:
            return False, "Item not in cart"
        if quantity <= 0:
            self.remove_item(product_id)
            return True, "Item removed"
        item = self._items[product_id]
        if quantity > item.product.stock:
            return False, f"Only {item.product.stock} available"
        item.quantity = quantity
        return True, "OK"

    def apply_discount(self, discount: Discount) -> Tuple[bool, str]:
        if not discount.is_valid(self.subtotal):
            return False, f"Minimum order {discount.min_order} not met"
        self._discount = discount
        return True, f"Discount {discount.code} applied: -{discount.percentage}%"

    @property
    def items(self) -> List[CartItem]:
        return list(self._items.values())

    @property
    def subtotal(self) -> float:
        return sum(item.subtotal for item in self._items.values())

    @property
    def total(self) -> float:
        base = self.subtotal
        if self._discount:
            base = self._discount.apply(base)
        return base

    @property
    def item_count(self) -> int:
        return sum(item.quantity for item in self._items.values())

    def clear(self) -> None:
        self._items.clear()
        self._discount = None


class PaymentProcessor:
    """Handles payment processing with multiple methods."""

    def __init__(self) -> None:
        self._processors: Dict[PaymentMethod, callable] = {
            PaymentMethod.CREDIT_CARD: self._process_credit_card,
            PaymentMethod.PAYPAL: self._process_paypal,
            PaymentMethod.BANK_TRANSFER: self._process_bank_transfer,
        }

    def process_payment(
        self, order: Order, method: PaymentMethod, payment_details: Dict
    ) -> Tuple[bool, str]:
        processor = self._processors.get(method)
        if processor is None:
            return False, f"Unsupported payment method: {method.value}"

        logger.info(f"Processing {method.value} payment for order {order.id}: {order.total:.2f}")

        success, message = processor(order.total, payment_details)
        if success:
            order.payment_method = method
            logger.info(f"Payment successful for order {order.id}")
        else:
            logger.error(f"Payment failed for order {order.id}: {message}")

        return success, message

    def _process_credit_card(
        self, amount: float, details: Dict
    ) -> Tuple[bool, str]:
        card_number = details.get("card_number", "")
        if len(card_number) < 13:
            return False, "Invalid card number"
        if amount <= 0:
            return False, "Invalid amount"
        # Simulate processing
        return True, f"Charged {amount:.2f} to card ending {card_number[-4:]}"

    def _process_paypal(self, amount: float, details: Dict) -> Tuple[bool, str]:
        email = details.get("email", "")
        if "@" not in email:
            return False, "Invalid PayPal email"
        return True, f"PayPal payment of {amount:.2f} from {email}"

    def _process_bank_transfer(
        self, amount: float, details: Dict
    ) -> Tuple[bool, str]:
        iban = details.get("iban", "")
        if len(iban) < 15:
            return False, "Invalid IBAN"
        return True, f"Bank transfer of {amount:.2f} initiated"


class OrderService:
    """Orchestrates order creation and lifecycle."""

    def __init__(
        self,
        catalog: ProductCatalog,
        payment: PaymentProcessor,
    ) -> None:
        self._catalog = catalog
        self._payment = payment
        self._orders: Dict[int, Order] = {}
        self._next_id = 1

    def create_order(
        self,
        cart: ShoppingCart,
        shipping_address: Address,
        payment_method: PaymentMethod,
        payment_details: Dict,
    ) -> Tuple[Optional[Order], str]:
        if not cart.items:
            return None, "Cart is empty"

        # Reserve stock
        reserved: List[Tuple[Product, int]] = []
        for item in cart.items:
            if not item.product.reserve(item.quantity):
                # Rollback
                for prod, qty in reserved:
                    prod.release(qty)
                return None, f"Insufficient stock for {item.product.name}"
            reserved.append((item.product, item.quantity))

        # Create order
        order = Order(
            id=self._next_id,
            customer=cart.customer,
            items=list(cart.items),
            shipping_address=shipping_address,
            discount=cart._discount,
        )
        self._next_id += 1

        # Process payment
        success, msg = self._payment.process_payment(
            order, payment_method, payment_details
        )
        if not success:
            # Rollback stock
            for prod, qty in reserved:
                prod.release(qty)
            return None, f"Payment failed: {msg}"

        # Confirm order
        order.confirm()
        self._orders[order.id] = order

        # Award loyalty points
        points = cart.customer.earn_points(order.total)
        logger.info(
            f"Order {order.id} created for {cart.customer.name}, "
            f"total={order.total:.2f}, points={points}"
        )

        cart.clear()
        return order, "Order created successfully"

    def get_order(self, order_id: int) -> Optional[Order]:
        return self._orders.get(order_id)

    def cancel_order(self, order_id: int) -> Tuple[bool, str]:
        order = self._orders.get(order_id)
        if order is None:
            return False, "Order not found"
        if order.cancel():
            return True, "Order cancelled"
        return False, "Cannot cancel order in current status"

    def get_customer_orders(self, customer_id: int) -> List[Order]:
        return [
            o for o in self._orders.values() if o.customer.id == customer_id
        ]

    def get_orders_by_status(self, status: OrderStatus) -> List[Order]:
        return [o for o in self._orders.values() if o.status == status]


class AnalyticsService:
    """Provides business analytics and reporting."""

    def __init__(self, order_service: OrderService) -> None:
        self._order_service = order_service

    def revenue_summary(self) -> Dict:
        orders = self._order_service._orders.values()
        confirmed = [
            o for o in orders
            if o.status in (OrderStatus.CONFIRMED, OrderStatus.SHIPPED, OrderStatus.DELIVERED)
        ]
        return {
            "total_orders": len(confirmed),
            "total_revenue": sum(o.total for o in confirmed),
            "avg_order_value": (
                sum(o.total for o in confirmed) / len(confirmed) if confirmed else 0
            ),
        }

    def top_products(self, limit: int = 5) -> List[Dict]:
        product_sales: Dict[int, Dict] = {}
        for order in self._order_service._orders.values():
            if order.status == OrderStatus.CANCELLED:
                continue
            for item in order.items:
                pid = item.product.id
                if pid not in product_sales:
                    product_sales[pid] = {
                        "product": item.product.name,
                        "quantity": 0,
                        "revenue": 0.0,
                    }
                product_sales[pid]["quantity"] += item.quantity
                product_sales[pid]["revenue"] += item.subtotal

        sorted_products = sorted(
            product_sales.values(), key=lambda x: x["revenue"], reverse=True
        )
        return sorted_products[:limit]

    def customer_lifetime_value(self, customer_id: int) -> float:
        orders = self._order_service.get_customer_orders(customer_id)
        return sum(
            o.total
            for o in orders
            if o.status != OrderStatus.CANCELLED
        )
