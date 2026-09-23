from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from authentication.permissions import get_or_create_profile
from venues.models import Venue

from .catalog import (
    CUSTOMER_SUGGESTIONS,
    PLATFORM_ADMIN_SUGGESTIONS,
    STAFF_SUGGESTIONS,
)
from .forms import ChatMessageForm
from .models import ChatConversation, ChatMessage
from .services import (
    build_customer_response,
    build_staff_response,
    get_user_venues,
)


def customer_chat(request, venue_id):
    venue = get_object_or_404(
        Venue.objects.filter(is_active=True),
        id=venue_id,
    )

    form = ChatMessageForm(
        request.POST or None,
        initial={"venue_id": venue.id},
    )

    if request.method == "POST" and form.is_valid():
        content = form.cleaned_data["message"]

        conversation = ChatConversation.objects.create(
            venue=venue,
            audience=ChatConversation.Audience.CUSTOMER,
            title=content[:80],
        )

        ChatMessage.objects.create(
            conversation=conversation,
            sender=ChatMessage.Sender.USER,
            content=content,
        )

        response_text, intent, metadata = build_customer_response(
            venue,
            content,
        )

        ChatMessage.objects.create(
            conversation=conversation,
            sender=ChatMessage.Sender.ASSISTANT,
            content=response_text,
            intent=intent,
            metadata=metadata,
        )

        return redirect(
            "assistant_chat:customer_conversation",
            conversation_id=conversation.id,
        )

    return render(
        request,
        "assistant_chat/customer_chat.html",
        {
            "venue": venue,
            "form": form,
            "suggestions": CUSTOMER_SUGGESTIONS,
        },
    )


def customer_conversation(request, conversation_id):
    conversation = get_object_or_404(
        ChatConversation.objects.select_related("venue"),
        id=conversation_id,
        audience=ChatConversation.Audience.CUSTOMER,
    )

    return render(
        request,
        "assistant_chat/customer_conversation.html",
        {
            "conversation": conversation,
            "suggestions": CUSTOMER_SUGGESTIONS,
        },
    )


@login_required
def staff_chat(request):
    profile = get_or_create_profile(request.user)
    venues = get_user_venues(request.user)

    if not venues.exists():
        raise PermissionDenied(
            "No tienes locales activos asignados."
        )

    if profile.is_platform_admin:
        suggestions = PLATFORM_ADMIN_SUGGESTIONS
    else:
        suggestions = STAFF_SUGGESTIONS

    form = ChatMessageForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        content = form.cleaned_data["message"]

        conversation = ChatConversation.objects.create(
            user=request.user,
            audience=ChatConversation.Audience.STAFF,
            title=content[:80],
        )

        ChatMessage.objects.create(
            conversation=conversation,
            sender=ChatMessage.Sender.USER,
            content=content,
        )

        response_text, intent, metadata = build_staff_response(
            request.user,
            content,
        )

        ChatMessage.objects.create(
            conversation=conversation,
            sender=ChatMessage.Sender.ASSISTANT,
            content=response_text,
            intent=intent,
            metadata=metadata,
        )

        return redirect(
            "assistant_chat:staff_conversation",
            conversation_id=conversation.id,
        )

    return render(
        request,
        "assistant_chat/staff_chat.html",
        {
            "form": form,
            "venues": venues,
            "suggestions": suggestions,
        },
    )


@login_required
def staff_conversation(request, conversation_id):
    conversation = get_object_or_404(
        ChatConversation.objects.select_related("user"),
        id=conversation_id,
        audience=ChatConversation.Audience.STAFF,
        user=request.user,
    )

    profile = get_or_create_profile(request.user)

    if profile.is_platform_admin:
        suggestions = PLATFORM_ADMIN_SUGGESTIONS
    else:
        suggestions = STAFF_SUGGESTIONS

    return render(
        request,
        "assistant_chat/staff_conversation.html",
        {
            "conversation": conversation,
            "suggestions": suggestions,
        },
    )


@login_required
@require_POST
def staff_continue_conversation(request, conversation_id):
    conversation = get_object_or_404(
        ChatConversation,
        id=conversation_id,
        audience=ChatConversation.Audience.STAFF,
        user=request.user,
    )

    form = ChatMessageForm(request.POST)

    if not form.is_valid():
        messages.error(
            request,
            "Escribe una consulta válida para continuar.",
        )
        return redirect(
            "assistant_chat:staff_conversation",
            conversation_id=conversation.id,
        )

    content = form.cleaned_data["message"]

    ChatMessage.objects.create(
        conversation=conversation,
        sender=ChatMessage.Sender.USER,
        content=content,
    )

    response_text, intent, metadata = build_staff_response(
        request.user,
        content,
    )

    ChatMessage.objects.create(
        conversation=conversation,
        sender=ChatMessage.Sender.ASSISTANT,
        content=response_text,
        intent=intent,
        metadata=metadata,
    )

    return redirect(
        "assistant_chat:staff_conversation",
        conversation_id=conversation.id,
    )