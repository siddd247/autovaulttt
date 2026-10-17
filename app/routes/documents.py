import os
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, send_from_directory, current_app
from werkzeug.utils import secure_filename
from app.models import db
from app.models.vehicle import Vehicle
from app.models.document import Document
from app.routes.auth import login_required, get_current_user

documents_bp = Blueprint('documents', __name__)

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@documents_bp.route('/documents')
@login_required
def index():
    user = get_current_user()
    vehicles = Vehicle.query.filter_by(user_id=user.id).order_by(Vehicle.created_at.desc()).all()
    selected_id = request.args.get('selected', type=int)

    selected_vehicle = None
    if selected_id:
        selected_vehicle = Vehicle.query.filter_by(id=selected_id, user_id=user.id).first()
    if not selected_vehicle and vehicles:
        selected_vehicle = vehicles[0]

    documents = []
    total_size = 0
    grouped_docs = {}

    if selected_vehicle:
        documents = Document.query.filter_by(vehicle_id=selected_vehicle.id).order_by(Document.uploaded_at.desc()).all()
        total_size = sum(d.file_size for d in documents)
        for d in documents:
            grouped_docs.setdefault(d.document_type, []).append(d)

    return render_template(
        'documents.html',
        user=user,
        vehicles=vehicles,
        selected_vehicle=selected_vehicle,
        documents=documents,
        total_size=total_size,
        grouped_docs=grouped_docs
    )

@documents_bp.route('/documents/upload', methods=['POST'])
@login_required
def upload():
    user = get_current_user()
    vehicle_id = request.form.get('vehicle_id', type=int)
    vehicle = db.session.get(Vehicle, vehicle_id)

    # Authorization verification (IDOR protection)
    if not vehicle or vehicle.user_id != user.id:
        abort(403)

    document_type = request.form.get('document_type', 'Other').strip()
    if 'document_file' not in request.files:
        flash('No file was provided in the upload request.', 'danger')
        return redirect(url_for('documents.index', selected=vehicle.id))

    file = request.files['document_file']
    if file.filename == '':
        flash('No file selected.', 'danger')
        return redirect(url_for('documents.index', selected=vehicle.id))

    if not allowed_file(file.filename):
        flash('Invalid file type! Allowed formats are: PDF, PNG, JPG, JPEG, WEBP.', 'danger')
        return redirect(url_for('documents.index', selected=vehicle.id))

    # Secure file processing: generate UUID disk identifier
    original_filename = secure_filename(file.filename)
    extension = original_filename.rsplit('.', 1)[1].lower()
    random_filename = f"{uuid.uuid4().hex}.{extension}"

    docs_upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'documents')
    os.makedirs(docs_upload_dir, exist_ok=True)

    disk_path = os.path.join(docs_upload_dir, random_filename)
    file.save(disk_path)
    file_size = os.path.getsize(disk_path)

    doc = Document(
        vehicle_id=vehicle.id,
        document_type=document_type,
        filename=random_filename,
        original_filename=original_filename,
        secure_storage_path=disk_path,
        file_size=file_size
    )
    db.session.add(doc)
    db.session.commit()

    flash(f'Document "{original_filename}" securely stored in vault!', 'success')
    return redirect(url_for('documents.index', selected=vehicle.id))

@documents_bp.route('/documents/download/<int:doc_id>')
@login_required
def download(doc_id):
    user = get_current_user()
    doc = db.session.get(Document, doc_id)

    if not doc:
        abort(404)

    # Authorization verification (IDOR protection)
    if doc.vehicle.user_id != user.id:
        abort(403)

    docs_upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'documents')
    file_path = os.path.join(docs_upload_dir, doc.filename)
    if not os.path.exists(file_path):
        flash('The requested document is no longer in ephemeral serverless storage.', 'warning')
        return redirect(url_for('documents.index', selected=doc.vehicle_id))

    return send_from_directory(
        docs_upload_dir,
        doc.filename,
        as_attachment=True,
        download_name=doc.original_filename
    )

@documents_bp.route('/documents/view/<int:doc_id>')
@login_required
def view(doc_id):
    user = get_current_user()
    doc = db.session.get(Document, doc_id)

    if not doc:
        abort(404)

    # Authorization verification (IDOR protection)
    if doc.vehicle.user_id != user.id:
        abort(403)

    docs_upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'documents')
    file_path = os.path.join(docs_upload_dir, doc.filename)
    if not os.path.exists(file_path):
        flash('The requested document is no longer in ephemeral serverless storage.', 'warning')
        return redirect(url_for('documents.index', selected=doc.vehicle_id))

    return send_from_directory(
        docs_upload_dir,
        doc.filename,
        as_attachment=False
    )

@documents_bp.route('/documents/delete/<int:doc_id>', methods=['POST'])
@login_required
def delete(doc_id):
    user = get_current_user()
    doc = db.session.get(Document, doc_id)

    if not doc:
        abort(404)

    # Authorization verification (IDOR protection)
    if doc.vehicle.user_id != user.id:
        abort(403)

    vehicle_id = doc.vehicle_id

    # Secure deletion from disk
    try:
        if os.path.exists(doc.secure_storage_path):
            os.remove(doc.secure_storage_path)
    except Exception:
        pass

    db.session.delete(doc)
    db.session.commit()
    flash(f'Document "{doc.original_filename}" deleted from vault.', 'info')
    return redirect(url_for('documents.index', selected=vehicle_id))
