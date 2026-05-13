from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsClinicalApiAuthorized(BasePermission):
	"""
	Default-deny API permission for protected clinical resources.

	Superusers keep break-glass operational access. Other users need an explicit
	clinical role group or the matching Django model permission.
	"""

	message = 'You do not have permission to access this clinical API resource.'

	read_roles = frozenset({
		'clinical_reader',
		'clinical_editor',
		'clinical_reviewer',
		'clinical_admin',
	})
	write_roles = frozenset({'clinical_editor', 'clinical_admin'})
	admin_roles = frozenset({'clinical_admin'})

	def has_permission(self, request, view):
		user = getattr(request, 'user', None)
		if not user or not user.is_authenticated:
			return False

		if user.is_superuser:
			return True

		model = self._get_model(view)
		if model is None:
			return False

		if request.method in SAFE_METHODS:
			allowed_roles = self._get_view_roles(view, 'clinical_read_roles', self.read_roles)
			return self._has_role(user, allowed_roles) or self._has_perm(user, model, 'view')

		action = self._permission_action(request.method)
		if action is None:
			return False

		allowed_roles = self._get_view_roles(view, 'clinical_write_roles', self.write_roles)
		return self._has_role(user, allowed_roles) or self._has_perm(user, model, action)

	def has_object_permission(self, request, view, obj):
		return self.has_permission(request, view)

	def _get_model(self, view):
		queryset = getattr(view, 'queryset', None)
		if queryset is not None:
			return queryset.model

		serializer_class = getattr(view, 'serializer_class', None)
		meta = getattr(serializer_class, 'Meta', None)
		return getattr(meta, 'model', None)

	def _get_view_roles(self, view, attribute_name, default_roles):
		roles = getattr(view, attribute_name, default_roles)
		return frozenset(roles) | self.admin_roles

	def _has_role(self, user, role_names):
		return user.groups.filter(name__in=role_names).exists()

	def _has_perm(self, user, model, action):
		permission = f'{model._meta.app_label}.{action}_{model._meta.model_name}'
		return user.has_perm(permission)

	def _permission_action(self, method):
		if method == 'POST':
			return 'add'
		if method in {'PUT', 'PATCH'}:
			return 'change'
		if method == 'DELETE':
			return 'delete'
		return None


class IsAuthenticatedReadWrite(IsClinicalApiAuthorized):
	pass
