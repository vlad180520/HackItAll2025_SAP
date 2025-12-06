"""Utility functions for the backend."""


def format_cost(cost: float) -> str:
    """
    Format cost with thousand separators (dot) and 2 decimal places.
    
    Args:
        cost: Cost value to format
        
    Returns:
        Formatted string like "12.345,67" for European format
        
    Examples:
        >>> format_cost(12345.67)
        '12.345,67'
        >>> format_cost(1234567.89)
        '1.234.567,89'
        >>> format_cost(123.45)
        '123,45'
    """
    # Format with 2 decimal places
    formatted = f"{cost:,.2f}"
    
    # Convert from US format (12,345.67) to European format (12.345,67)
    # Replace comma with temporary marker
    formatted = formatted.replace(',', '|')
    # Replace decimal point with comma
    formatted = formatted.replace('.', ',')
    # Replace temporary marker with dot
    formatted = formatted.replace('|', '.')
    
    return formatted
