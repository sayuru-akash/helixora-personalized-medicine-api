from django.db.models import Q


def has_clinical_admin_scope(user) -> bool:
	return bool(
		user
		and user.is_authenticated
		and (user.is_superuser or user.groups.filter(name='clinical_admin').exists())
	)


class PatientScopedAdminMixin:
	patient_scope_filter = ''

	def get_queryset(self, request):
		queryset = super().get_queryset(request)
		if has_clinical_admin_scope(request.user):
			return queryset
		if not self.patient_scope_filter:
			return queryset.none()
		return queryset.filter(**{self.patient_scope_filter: request.user}).distinct()


class AuditPatientScopedAdminMixin(PatientScopedAdminMixin):
	def get_queryset(self, request):
		queryset = super(PatientScopedAdminMixin, self).get_queryset(request)
		if has_clinical_admin_scope(request.user):
			return queryset
		return queryset.filter(
			Q(patient__authorized_users=request.user)
			| Q(recommendation__patient__authorized_users=request.user)
		).distinct()
