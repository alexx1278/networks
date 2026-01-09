#!/usr/bin/env python3
"""
Основной модуль для обнаружения сетевых устройств
"""

from .engine import NetworkDiscoveryEngine

# Для обратной совместимости
NetworkDiscovery = NetworkDiscoveryEngine

__all__ = ['NetworkDiscovery', 'NetworkDiscoveryEngine']