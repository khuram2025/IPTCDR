from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from .models import Extension, Company

class ExtensionResource(resources.ModelResource):
    company = fields.Field(
        column_name='company__name',
        attribute='company',
        widget=ForeignKeyWidget(Company, 'name')
    )

    class Meta:
        model = Extension
        import_id_fields = ('extension',)
        fields = ('extension', 'first_name', 'last_name', 'full_name', 'email', 'company')

    def before_import_row(self, row, **kwargs):
        company_name = row.get('company__name')
        if company_name:
            company, created = Company.objects.get_or_create(name__iexact=company_name, defaults={'name': company_name})
            row['company'] = company.id
