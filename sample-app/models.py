"""Domain models for e-commerce sample application."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional


class OrderStatus(Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class PaymentMethod(Enum):
    CREDIT_CARD = "credit_card"
    PAYPAL = "paypal"
    BANK_TRANSFER = "bank_transfer"


@dataclass
class Product:
    id: int
    name: str
    price: float
    stock: int = 0
    category: str = ""
    description: str = ""

    def is_available(self) -> bool:
        return self.stock > 0

    def reserve(self, quantity: int) -> bool:
        if self.stock >= quantity:
            self.stock -= quantity
            return True
        return False

    def release(self, quantity: int) -> None:
        self.stock += quantity


@dataclass
class CartItem:
    product: Product
    quantity: int = 1

    @property
    def subtotal(self) -> float:
        return self.product.price * self.quantity


@dataclass
class Discount:
    code: str
    percentage: float
    min_order: float = 0.0
    max_uses: int = -1
    uses: int = 0

    def is_valid(self, order_total: float) -> bool:
        if self.max_uses > 0 and self.uses >= self.max_uses:
            return False
        return order_total >= self.min_order

    def apply(self, total: float) -> float:
        if not self.is_valid(total):
            return total
        self.uses += 1
        return total * (1 - self.percentage / 100)


@dataclass
class Address:
    street: str
    city: str
    zip_code: str
    country: str = "PL"

    def format(self) -> str:
        return f"{self.street}, {self.zip_code} {self.city}, {self.country}"


@dataclass
class Customer:
    id: int
    name: str
    email: str
    addresses: List[Address] = field(default_factory=list)
    loyalty_points: int = 0

    def add_address(self, address: Address) -> None:
        self.addresses.append(address)

    def primary_address(self) -> Optional[Address]:
        return self.addresses[0] if self.addresses else None

    def earn_points(self, amount: float) -> int:
        points = int(amount / 10)
        self.loyalty_points += points
        return points


@dataclass
class Order:
    id: int
    customer: Customer
    items: List[CartItem] = field(default_factory=list)
    status: OrderStatus = OrderStatus.PENDING
    discount: Optional[Discount] = None
    shipping_address: Optional[Address] = None
    created_at: datetime = field(default_factory=datetime.now)
    payment_method: Optional[PaymentMethod] = None

    @property
    def subtotal(self) -> float:
        return sum(item.subtotal for item in self.items)

    @property
    def total(self) -> float:
        base = self.subtotal
        if self.discount:
            base = self.discount.apply(base)
        return base

    def confirm(self) -> bool:
        if self.status != OrderStatus.PENDING:
            return False
        if not self.items:
            return False
        if not self.shipping_address:
            return False
        self.status = OrderStatus.CONFIRMED
        return True

    def cancel(self) -> bool:
        if self.status in (OrderStatus.SHIPPED, OrderStatus.DELIVERED):
            return False
        for item in self.items:
            item.product.release(item.quantity)
        self.status = OrderStatus.CANCELLED
        return True
