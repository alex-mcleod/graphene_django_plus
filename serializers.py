from rest_framework.serializers import IntegerField, ListField, PrimaryKeyRelatedField
from graphene_django.converter import convert_django_field
from graphene_django.rest_framework.serializer_converter import get_graphene_type_from_serializer_field

from ..api.simple_api.serializers import ModelSerializer as ModelMutationSerializer

from .types import DjangoFileType


import graphene
from rest_framework import serializers
from myagi_common.api.fields import MyagiImageField
from django.db import models as dbmodels
from imagekit.models import ProcessedImageField

from graphene_file_upload.scalars import Upload


class ManyToManyIDField(ListField):
    child = IntegerField()


@get_graphene_type_from_serializer_field.register(MyagiImageField)
def convert_serializer_field_to_string(field):
    return graphene.String

@get_graphene_type_from_serializer_field.register(MyagiImageField)
def convert_serializer_to_field(field):
    return Upload

# Register image and file types to map to Django file type which supports
# file based uploads.
@convert_django_field.register(dbmodels.ImageField)
@convert_django_field.register(dbmodels.FileField)
@convert_django_field.register(MyagiImageField)
@convert_django_field.register(serializers.ImageField)
@convert_django_field.register(ProcessedImageField)
def convert_file_to_url(field, registry=None):
    return DjangoFileType(description=field.help_text, required=not field.null)
