# -*- coding: utf-8 -*-
import json
import hashlib
from api.models import Claimant, IdentityProvider
from api.whoami import WhoAmI
from django.db import transaction
from django.utils import timezone
from django_redis import get_redis_connection
from datetime import timedelta
from dacite import from_dict


def session_as_dict(request):
    this_session = {
        "_session_key": request.session.session_key,
    }
    for k in request.session.keys():
        this_session[k] = request.session[k]
    return this_session


def get_session_store():
    return get_redis_connection("default")


def get_session_expires_at(session_key):
    r = get_session_store()
    # TODO there's gotta be a function somewhere to derive this...
    key = f"claimantsapi:secure:1:django.contrib.sessions.cache{session_key}"
    ttl = r.ttl(key)
    return timezone.now() + timedelta(0, ttl)


def register_local_login(request):
    request.session["authenticated"] = True
    whoami = {}
    if request.content_type == "application/json":
        payload = json.loads(request.body)
    else:
        payload = request.POST

    for k in payload.keys():
        if "." in k:
            k_parts = k.split(".")
            if k_parts[0] not in whoami:
                whoami[k_parts[0]] = {}
            whoami[k_parts[0]][k_parts[1]] = payload[k]
        else:
            whoami[k] = payload[k]

    if whoami["IAL"] == "2":
        whoami["verified_at"] = str(timezone.now().isoformat())

    request.session["whoami"] = whoami
    local_idp = local_identity_provider()
    if "email" in whoami and len(whoami["email"]):
        xid = hash_idp_user_xid(whoami["email"])
        with transaction.atomic():
            claimant, _ = Claimant.objects.get_or_create(
                idp_user_xid=xid, idp=local_idp
            )
            claimant.events.create(
                category=Claimant.EventCategories.LOGGED_IN, description=whoami["IAL"]
            )
            claimant.bump_IAL_if_necessary(whoami["IAL"])

        whoami["claimant_id"] = xid
    whoami["identity_provider"] = local_idp.name
    return from_dict(data_class=WhoAmI, data=whoami)


def hash_idp_user_xid(user_xid):
    return hashlib.sha256(user_xid.encode("utf-8")).hexdigest()


def local_identity_provider():
    idp, _ = IdentityProvider.objects.get_or_create(name="Local")
    return idp
