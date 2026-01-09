#!/usr/bin/env python3
"""
Network Device Discovery Package
Автоматическое обнаружение сетевых устройств и создание инвентаря
"""

__version__ = '2.0.0'
__author__ = 'Network Automation Team'
__description__ = 'Network Device Discovery and Inventory Builder with SSH and Telnet support'

from .discovery import NetworkDiscovery
from .models.device import DeviceCredentials, DiscoveredDevice, Protocol
from .inventory.loader import DataLoader
from .inventory.saver import InventorySaver

__all__ = [
    'NetworkDiscovery',
    'DeviceCredentials',
    'DiscoveredDevice',
    'Protocol',
    'DataLoader',
    'InventorySaver'
]