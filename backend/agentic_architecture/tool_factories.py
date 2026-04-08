# backend/agents/tool_factories.py

from agents import function_tool
from typing import Dict, Any, Optional
import asyncio

def create_tools(student_id: int, db_connection):
    """
    Create tools with student_id and db_connection bound via closure
    This is the KEY - tools need access to context
    """
    
    @function_tool
    def get_course_data(course_name: str) -> Dict[str, Any]:
        """Get course data for current student"""
        # Import inside function to avoid circular imports
        from .tools import get_course_data as original_get_course_data
        
        # Run async function synchronously
        return asyncio.run(original_get_course_data(
            course_name=course_name,
            student_id=student_id,
            db_connection=db_connection
        ))
    
    @function_tool
    def get_performance_data(course_name: str) -> Dict[str, Any]:
        """Get performance data for current student"""
        from .tools import get_performance_data as original_get_performance_data
        
        return asyncio.run(original_get_performance_data(
            course_name=course_name,
            student_id=student_id,
            db_connection=db_connection
        ))
    
    @function_tool
    def get_course_analysis(course_name: Optional[str] = None) -> Dict[str, Any]:
        """Get course analysis for current student"""
        from .tools import get_course_analysis as original_get_course_analysis
        
        return asyncio.run(original_get_course_analysis(
            course_name=course_name,
            student_id=student_id,
            db_connection=db_connection
        ))
    
    return [get_course_data, get_performance_data, get_course_analysis]