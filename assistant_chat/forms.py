from django import forms


class ChatMessageForm(forms.Form):
    message = forms.CharField(
        max_length=600,
        widget=forms.Textarea(
            attrs={
                "rows": 2,
                "placeholder": "Escribe tu consulta...",
            }
        ),
    )

    venue_id = forms.IntegerField(
        required=False,
        widget=forms.HiddenInput(),
    )