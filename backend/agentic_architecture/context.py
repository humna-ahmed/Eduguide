# backend/agents/context.py

"""Global context for tools to access student_id and db_connection"""

_current_context = {}

def set_context(student_id: int, db_connection):
    """Set global context before running agents"""
    _current_context['student_id'] = student_id
    _current_context['db_connection'] = db_connection

def get_context():
    """Get current context"""
    return _current_context.get('student_id'), _current_context.get('db_connection')