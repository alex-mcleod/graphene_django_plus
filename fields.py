from graphene import Field


class PermissionedTypeField(Field):
    def __init__(self, type, *args, **kwargs):
        assert hasattr(
            type, "ensure_user_can_view_instance"
        ), "Types which are passed to PermissionField should sub-class `PermissionedType`"
        # Keep base_type, as it is used to do permissions check. `Field` class may wrap
        # `type` in a `NonNull` container.
        self.base_type = type
        super().__init__(type, *args, **kwargs)

    def get_resolver(self, parent_resolver):
        res = super().get_resolver(parent_resolver)

        def resolve_with_permission_check(root, info, **kwargs):
            inst = res(root, info, **kwargs)
            if inst:
                self.base_type.ensure_user_can_view_instance(info, inst)
            return inst

        return resolve_with_permission_check
