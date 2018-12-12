import traceback
from graphene_file_upload.django import FileUploadGraphQLView
from raven.contrib.django.raven_compat.models import client as sentry_client

class ExceptionHandlingGraphQLView(FileUploadGraphQLView):

    def execute_graphql_request(self, *args, **kwargs):
        """Extracts any exceptions. Sends them to Sentry and also prints them to the console."""
        result = super().execute_graphql_request(*args, **kwargs)
        if result and result.errors:
            for error in result.errors:
                try:
                    raise error.original_error
                except Exception as e:
                    sentry_client.captureException()
                    tb = traceback.format_exc()
                    print("Exception was caught by GraphQL Core. Original error:")
                    print(tb)
        return result
