from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views import View
from django.db import connection
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError
import os
import json
import re

from .services import ConfigurationService
from .models import DataSource, DataSourcePermission, WriteBackRequest

@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(login_required, name='dispatch')
class DataSourceConfigView(View):
    """API view for data source configuration management"""
    
    def get(self, request, source_id=None):
        """Get data source configuration(s)"""
        if source_id:
            # Get specific data source
            config = ConfigurationService.get_data_source_config(
                source_id, 
                request.user
            )
            if config:
                return JsonResponse({'success': True, 'data': config})
            else:
                return JsonResponse(
                    {'success': False, 'error': 'Data source not found or access denied'}, 
                    status=404
                )
        else:
            # Get all active data sources
            configs = ConfigurationService.get_active_data_sources(request.user)
            return JsonResponse({'success': True, 'data': configs})
    
    def post(self, request, source_id):
        """Update data source configuration"""
        try:
            config_data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse(
                {'success': False, 'error': 'Invalid JSON'}, 
                status=400
            )
        
        # Validate configuration
        if 'search_config' in config_data:
            search_validation = ConfigurationService.validate_search_config(
                config_data['search_config']
            )
            if not search_validation['valid']:
                return JsonResponse(
                    {
                        'success': False, 
                        'error': 'Invalid search configuration',
                        'details': search_validation['errors']
                    }, 
                    status=400
                )
        
        if 'graph_config' in config_data:
            graph_validation = ConfigurationService.validate_graph_config(
                config_data['graph_config']
            )
            if not graph_validation['valid']:
                return JsonResponse(
                    {
                        'success': False, 
                        'error': 'Invalid graph configuration',
                        'details': graph_validation['errors']
                    }, 
                    status=400
                )
        
        # Update configuration
        success = ConfigurationService.update_data_source_config(
            source_id, 
            config_data, 
            request.user
        )
        
        if success:
            return JsonResponse({'success': True})
        else:
            return JsonResponse(
                {'success': False, 'error': 'Failed to update configuration or access denied'}, 
                status=403
            )

@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(login_required, name='dispatch')
class ConfigValidationView(View):
    """API view for configuration validation"""
    
    def post(self, request):
        """Validate configuration data"""
        try:
            config_data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse(
                {'success': False, 'error': 'Invalid JSON'}, 
                status=400
            )
        
        results = {}
        
        # Validate search config if provided
        if 'search_config' in config_data:
            results['search_config'] = ConfigurationService.validate_search_config(
                config_data['search_config']
            )
        
        # Validate graph config if provided
        if 'graph_config' in config_data:
            results['graph_config'] = ConfigurationService.validate_graph_config(
                config_data['graph_config']
            )
        
        # Overall validity
        results['valid'] = all(
            result.get('valid', False) for result in results.values()
        )
        
        return JsonResponse({'success': True, 'data': results})

@require_http_methods(["GET"])
@login_required
def get_data_source_types(request):
    """Get available data source types with their default configurations"""
    source_types = {
        'wikidata': {
            'display_name': 'Wikidata',
            'description': 'Free knowledge base from the world',
            'default_search_config': {
                'fields': {
                    'title': {'field': 'label', 'display': 'bold', 'required': True},
                    'subtitle': {'field': 'id', 'display': 'subtitle', 'required': True},
                    'description': {'field': 'description', 'display': 'description', 'required': False},
                    'source': {'field': 'author', 'display': 'tag', 'required': True},
                    'confidence': {'field': 'confidence', 'display': 'badge', 'required': False}
                },
                'limit': 10,
                'min_query_length': 2,
                'debounce_ms': 300
            },
            'required_fields': ['api_url']
        },
        'oxigraph': {
            'display_name': 'Oxigraph RDF Store',
            'description': 'Oxigraph SPARQL endpoint',
            'default_search_config': {
                'fields': {
                    'title': {'field': 'label', 'display': 'bold', 'required': True},
                    'subtitle': {'field': 'uri', 'display': 'subtitle', 'required': True},
                    'description': {'field': 'comment', 'display': 'description', 'required': False},
                    'source': {'field': 'type', 'display': 'tag', 'required': True},
                    'graph': {'field': 'graph', 'display': 'badge', 'required': False}
                },
                'limit': 10,
                'min_query_length': 2,
                'debounce_ms': 300
            },
            'required_fields': ['endpoint_url']
        },
        'fuseki': {  # Legacy alias for backwards compatibility
            'display_name': 'Oxigraph RDF Store',
            'description': 'Oxigraph SPARQL endpoint (legacy source type: fuseki)',
            'default_search_config': {
                'fields': {
                    'title': {'field': 'label', 'display': 'bold', 'required': True},
                    'subtitle': {'field': 'uri', 'display': 'subtitle', 'required': True},
                    'description': {'field': 'comment', 'display': 'description', 'required': False},
                    'source': {'field': 'type', 'display': 'tag', 'required': True},
                    'graph': {'field': 'graph', 'display': 'badge', 'required': False}
                },
                'limit': 10,
                'min_query_length': 2,
                'debounce_ms': 300
            },
            'required_fields': ['endpoint_url']
        },
        'django_db': {
            'display_name': 'Django Database',
            'description': 'Internal Django database models',
            'default_search_config': {
                'fields': {
                    'title': {'field': 'name', 'display': 'bold', 'required': True},
                    'subtitle': {'field': 'id', 'display': 'subtitle', 'required': True},
                    'description': {'field': 'description', 'display': 'description', 'required': False},
                    'source': {'field': 'model', 'display': 'tag', 'required': True},
                    'created': {'field': 'created_at', 'display': 'badge', 'required': False}
                },
                'limit': 10,
                'min_query_length': 2,
                'debounce_ms': 300
            },
            'required_fields': ['model_name']
        }
    }
    
    return JsonResponse({'success': True, 'data': source_types})

@require_http_methods(["POST"])
@login_required
def create_default_django_sources(request):
    """Create default Django DB data sources"""
    try:
        from .services import ConfigurationService
        
        created = ConfigurationService.create_default_django_sources(request.user)
        
        if created:
            return JsonResponse({
                'success': True, 
                'message': 'Default Django data sources created successfully'
            })
        else:
            return JsonResponse({
                'success': True, 
                'message': 'Default Django data sources already exist'
            })
            
    except Exception as e:
        return JsonResponse(
            {'success': False, 'error': str(e)}, 
            status=500
        )


# ---------------------------------------------------------------------------
# Minimal data-source + write-back endpoints used by Django URLs.
# These are lightweight facsimiles so the router endpoints resolve cleanly.
# ---------------------------------------------------------------------------

def _serialize_data_source(ds: DataSource):
    return {
        'id': ds.id,
        'name': ds.name,
        'type': ds.type,
        'description': ds.description,
        'is_active': ds.is_active,
        'allow_write_back': ds.allow_write_back,
        'created_at': ds.created_at,
        'created_by': ds.created_by.username if ds.created_by_id else None,
    }

def _get_effective_user(request):
    """
    Resolve the user context for permission checks.
    FastAPI internal calls can pass X-User-ID after JWT validation.
    """
    requested_user_id = request.headers.get('X-User-ID')
    if requested_user_id and request.user.is_superuser:
        try:
            user = User.objects.filter(pk=int(requested_user_id), is_active=True).first()
            if user:
                return user
        except (TypeError, ValueError):
            pass
    return request.user


@login_required
@require_http_methods(["GET", "POST"])
def data_sources_list(request):
    """List accessible sources or create a new Ontop source."""
    effective_user = _get_effective_user(request)
    if request.method == "POST":
        payload = _parse_json_body(request)
        if payload is None:
            return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

        source_type = (payload.get("type") or payload.get("source_type") or "").strip().lower()
        if source_type != "ontop":
            return JsonResponse({'success': False, 'error': 'Only Ontop source creation is supported'}, status=400)

        can_create = (
            effective_user.is_superuser
            or ConfigurationService._user_in_allowed_domains(  # noqa: SLF001
                effective_user,
                ConfigurationService._default_ontop_domains(),  # noqa: SLF001
            )
        )
        if not can_create:
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)

        name = str(payload.get("name", "")).strip()
        if not name:
            return JsonResponse({'success': False, 'error': 'Name is required'}, status=400)
        if DataSource.objects.filter(name=name).exists():
            return JsonResponse({'success': False, 'error': 'A datasource with this name already exists'}, status=400)

        connection_config = payload.get("connection_config") or {}
        security_policy = payload.get("security_policy") or {}
        ui_config = payload.get("ui_config") or {}
        if "query_domains" not in security_policy:
            security_policy["query_domains"] = ConfigurationService._default_ontop_domains()  # noqa: SLF001
        if "manage_domains" not in security_policy:
            security_policy["manage_domains"] = ConfigurationService._default_ontop_domains()  # noqa: SLF001

        ds = DataSource.objects.create(
            name=name,
            type="ontop",
            description=str(payload.get("description", "")).strip(),
            connection_config=connection_config,
            security_policy=security_policy,
            ui_config=ui_config,
            created_by=effective_user,
            is_active=True,
        )
        DataSourcePermission.objects.get_or_create(
            data_source=ds,
            user=effective_user,
            permission='query',
            defaults={'granted_by': effective_user, 'requires_approval': False},
        )
        DataSourcePermission.objects.get_or_create(
            data_source=ds,
            user=effective_user,
            permission='view',
            defaults={'granted_by': effective_user, 'requires_approval': False},
        )
        serialized = ConfigurationService.get_data_source_config(ds.id, effective_user)
        return JsonResponse({'success': True, 'data': serialized}, status=201)

    data = ConfigurationService.get_active_data_sources(effective_user)
    return JsonResponse({'success': True, 'data': data})


@login_required
@require_http_methods(["GET"])
def data_source_detail(request, source_id: int):
    """Return details for a single data source if the effective user can view it."""
    effective_user = _get_effective_user(request)
    config = ConfigurationService.get_data_source_config(source_id, effective_user)
    if not config:
        return JsonResponse({'success': False, 'error': 'Data source not found'}, status=404)
    return JsonResponse({'success': True, 'data': config})


@login_required
@require_http_methods(["GET"])
def data_source_permissions(request, source_id: int):
    """Return explicit row-level permissions for the effective user."""
    effective_user = _get_effective_user(request)
    perms = DataSourcePermission.objects.filter(data_source_id=source_id, user=effective_user)
    data = [
        {
            'permission': perm.permission,
            'row_level_filter': perm.row_level_filter,
            'column_level_filter': perm.column_level_filter,
            'requires_approval': perm.requires_approval,
        }
        for perm in perms
    ]
    return JsonResponse({'success': True, 'data': data})


@login_required
@require_http_methods(["POST"])
def data_source_update(request, source_id: int):
    """Update a data source configuration if the effective user can manage it."""
    effective_user = _get_effective_user(request)
    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

    allowed_fields = {
        'search_config',
        'graph_config',
        'field_mappings',
        'ui_config',
        'write_back_config',
        'allow_write_back',
        'connection_config',
        'security_policy',
    }
    filtered_payload = {k: v for k, v in payload.items() if k in allowed_fields}
    if not filtered_payload:
        return JsonResponse({'success': False, 'error': 'No updatable fields provided'}, status=400)

    updated = ConfigurationService.update_data_source_config(source_id, filtered_payload, effective_user)
    if not updated:
        return JsonResponse({'success': False, 'error': 'Access denied or source not found'}, status=403)

    refreshed = ConfigurationService.get_data_source_config(source_id, effective_user)
    return JsonResponse({'success': True, 'data': refreshed})


def _parse_json_body(request):
    try:
        return json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return None


def _has_valid_internal_key(request) -> bool:
    expected = os.environ.get('INTERNAL_API_KEY', '')
    if not expected:
        return False
    provided = request.headers.get('X-Internal-API-Key', '')
    return provided == expected


@login_required
@require_http_methods(["POST"])
def create_write_back_request(request):
    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

    required = ['source_id', 'operation', 'table_name', 'new_values']
    missing = [field for field in required if field not in payload]
    if missing:
        return JsonResponse(
            {'success': False, 'error': f"Missing required fields: {', '.join(missing)}"},
            status=400,
        )
    operation = str(payload.get('operation', '')).strip().lower()
    if operation not in {'insert', 'update', 'delete'}:
        return JsonResponse({'success': False, 'error': 'Invalid operation'}, status=400)
    table_name = str(payload.get('table_name', '')).strip()
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', table_name):
        return JsonResponse({'success': False, 'error': 'Invalid table_name'}, status=400)
    if not isinstance(payload.get('new_values'), dict):
        return JsonResponse({'success': False, 'error': 'new_values must be an object'}, status=400)
    if payload.get('old_values') is not None and not isinstance(payload.get('old_values'), dict):
        return JsonResponse({'success': False, 'error': 'old_values must be an object'}, status=400)

    try:
        source = DataSource.objects.get(pk=payload['source_id'], is_active=True)
    except DataSource.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Data source not found'}, status=404)

    if not source.allow_write_back:
        return JsonResponse({'success': False, 'error': 'Write-back not enabled for this source'}, status=403)

    user = _get_effective_user(request)
    has_permission = (
        user.is_superuser
        or DataSourcePermission.objects.filter(
            data_source=source,
            user=user,
            permission__in=['write_back', 'admin'],
        ).exists()
    )
    if not has_permission:
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)

    request_obj = WriteBackRequest.objects.create(
        data_source=source,
        requested_by=user,
        operation=operation,
        table_name=table_name,
        primary_key=payload.get('primary_key', ''),
        old_values=payload.get('old_values'),
        new_values=payload['new_values'],
        status='pending',
    )

    return JsonResponse(
        {
            'success': True,
            'data': {
                'id': request_obj.id,
                'status': request_obj.status,
                'operation': request_obj.operation,
                'created_at': request_obj.created_at,
            },
        },
        status=201,
    )


@login_required
@require_http_methods(["GET"])
def write_back_requests_list(request):
    user = _get_effective_user(request)
    if user.is_superuser:
        queryset = WriteBackRequest.objects.select_related('data_source', 'requested_by').all()
    else:
        admin_source_ids = DataSourcePermission.objects.filter(
            user=user,
            permission='admin',
        ).values_list('data_source_id', flat=True)
        queryset = WriteBackRequest.objects.select_related('data_source', 'requested_by').filter(
            requested_by=user
        ) | WriteBackRequest.objects.select_related('data_source', 'requested_by').filter(
            data_source_id__in=admin_source_ids
        )
        queryset = queryset.distinct()

    data = [
        {
            'id': req.id,
            'source_id': req.data_source_id,
            'source_name': req.data_source.name,
            'requested_by': req.requested_by.username,
            'operation': req.operation,
            'table_name': req.table_name,
            'status': req.status,
            'created_at': req.created_at,
            'approved_at': req.approved_at,
        }
        for req in queryset.order_by('-created_at')[:200]
    ]
    return JsonResponse({'success': True, 'data': data})


@login_required
@require_http_methods(["GET"])
def write_back_request_detail(request, request_id: int):
    user = _get_effective_user(request)
    req = WriteBackRequest.objects.select_related('data_source', 'requested_by', 'approved_by').filter(
        pk=request_id
    ).first()
    if not req:
        return JsonResponse({'success': False, 'error': 'Request not found'}, status=404)

    can_view = user.is_superuser or req.requested_by_id == user.id or DataSourcePermission.objects.filter(
        data_source_id=req.data_source_id,
        user=user,
        permission='admin',
    ).exists()
    if not can_view:
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)

    return JsonResponse(
        {
            'success': True,
            'data': {
                'id': req.id,
                'source_id': req.data_source_id,
                'source_name': req.data_source.name,
                'requested_by': req.requested_by.username,
                'operation': req.operation,
                'table_name': req.table_name,
                'primary_key': req.primary_key,
                'old_values': req.old_values,
                'new_values': req.new_values,
                'status': req.status,
                'approved_by': req.approved_by.username if req.approved_by else None,
                'approved_at': req.approved_at,
                'rejection_reason': req.rejection_reason,
                'executed_at': req.executed_at,
                'execution_result': req.execution_result,
                'error_message': req.error_message,
                'created_at': req.created_at,
                'updated_at': req.updated_at,
            },
        }
    )


@login_required
@require_http_methods(["POST"])
def approve_write_back_request(request, request_id: int):
    user = _get_effective_user(request)
    req = WriteBackRequest.objects.select_related('data_source').filter(pk=request_id).first()
    if not req:
        return JsonResponse({'success': False, 'error': 'Request not found'}, status=404)

    has_admin_permission = user.is_superuser or DataSourcePermission.objects.filter(
        data_source_id=req.data_source_id,
        user=user,
        permission='admin',
    ).exists()
    if not has_admin_permission:
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)

    payload = _parse_json_body(request) or {}
    action = (payload.get('action') or 'approve').lower()

    if req.status not in {'pending', 'approved'}:
        return JsonResponse({'success': False, 'error': f'Cannot process request in status {req.status}'}, status=400)

    if action == 'reject':
        req.status = 'rejected'
        req.rejection_reason = payload.get('reason', 'Rejected by approver')
    else:
        req.status = 'approved'
        req.rejection_reason = ''

    req.approved_by = user
    req.approved_at = timezone.now()
    req.save(update_fields=['status', 'rejection_reason', 'approved_by', 'approved_at', 'updated_at'])

    return JsonResponse(
        {
            'success': True,
            'data': {
                'id': req.id,
                'status': req.status,
                'approved_by': user.username,
                'approved_at': req.approved_at,
            },
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def validate_jwt(request):
    """Validate a JWT supplied by FastAPI and return stable identity fields."""
    if not _has_valid_internal_key(request):
        return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)

    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

    token = payload.get('token')
    if not token:
        return JsonResponse({'success': False, 'error': 'Missing token'}, status=400)

    try:
        access = AccessToken(token)
        user_id = access.get('user_id')
        if not user_id:
            return JsonResponse({'success': False, 'error': 'Token missing user_id'}, status=401)
        user = User.objects.filter(pk=user_id, is_active=True).first()
        if not user:
            return JsonResponse({'success': False, 'error': 'User not found'}, status=401)
        return JsonResponse({
            'success': True,
            'valid': True,
            'user_id': user.id,
            'username': user.username,
        })
    except TokenError:
        return JsonResponse({'success': False, 'valid': False, 'error': 'Invalid token'}, status=401)


@csrf_exempt
@require_http_methods(["POST"])
def sql_query(request):
    """
    Internal read-only SQL endpoint used by FastAPI.
    Contract: body {"sql": "...", "user_id": <int>}
    """
    if not _has_valid_internal_key(request):
        return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)

    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

    sql = (payload.get('sql') or '').strip()
    if not sql:
        return JsonResponse({'success': False, 'error': 'Missing SQL'}, status=400)

    lowered = sql.lower()
    if not lowered.startswith('select'):
        return JsonResponse({'success': False, 'error': 'Only SELECT queries are allowed'}, status=400)
    if ';' in sql:
        return JsonResponse({'success': False, 'error': 'Multiple statements are not allowed'}, status=400)
    normalized = re.sub(r'\s+', ' ', lowered)
    blocked_patterns = (
        r'\bpg_read_file\s*\(',
        r'\bpg_ls_dir\s*\(',
        r'\bpg_sleep\s*\(',
        r'\bdblink\s*\(',
        r'\bcopy\b',
        r'\binto\s+outfile\b',
    )
    if any(re.search(pattern, normalized) for pattern in blocked_patterns):
        return JsonResponse({'success': False, 'error': 'Query contains blocked SQL pattern'}, status=400)

    try:
        with connection.cursor() as cursor:
            # Constrain query runtime for this transaction to reduce abuse/blast radius.
            cursor.execute("SET LOCAL statement_timeout = %s", [5000])
            cursor.execute(sql)
            columns = [col[0] for col in (cursor.description or [])]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return JsonResponse({'success': True, 'results': rows, 'total': len(rows)})
    except Exception as exc:
        return JsonResponse({'success': False, 'error': str(exc)}, status=400)


@csrf_exempt
@require_http_methods(["POST"])
def sql_execute(request):
    """Reserved for future write execution service."""
    if not _has_valid_internal_key(request):
        return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)

    return JsonResponse(
        {'success': False, 'error': 'Write execution not implemented in Django service'},
        status=501,
    )
