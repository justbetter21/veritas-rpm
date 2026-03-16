"""
veritas_rpm.services — External-facing service layer.

Currently contains:
    DashboardService — routes SystemDecisions to human roles and accepts
                       clinician feedback.
"""

from veritas_rpm.services.dashboard_service import DashboardService

__all__ = ["DashboardService"]
