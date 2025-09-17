## Reusable Date Range Filter UI

To use the date range filter UI across your Django templates, simply include the following line where you want the filter to appear:

```
{% include "cdr/date_range_filter.html" %}
```

This will render the standard date range filter form. Make sure the necessary context variables (`time_period`, `custom_date_range`, `limit`, etc.) are available in your view.
