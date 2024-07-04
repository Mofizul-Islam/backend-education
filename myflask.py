import json
import os
# import services.mcq_generator
# services.mcq_generator.generate_mcqs()
from services.mcq_generator import generate_mcqs
import bleach
from flask import request, make_response
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS, cross_origin
from markdown import markdown
from werkzeug.utils import secure_filename
from uuid import uuid1
import logging
from aihelper import get_file_name_with_id, get_resume_categories
from mydb import exec_query, run_select, update_table_fields
from myutils import (
    DB_SCHEMA,
    fetch_emails_and_categorize,
    make_dict,
    fields_as,
    table_diff_in_html,
    upload_file_to_cloud,
    download_file_from_cloud,
    RESUME_ASSISTANCE_ID,
    LEASE_ASSISTANCE_ID,
    EMAIL_ASSISTANCE_ID,
    update_lease_agreement_with_template,
    create_folder_not_exist,
    response,
    download_from_cloud
)
from ocr import extract_text_from_pdf, get_docx_text
# from ocr import extract_text_from_docx, Extract_pdf
# from workhorse import test5, delete_record
# from externals import fill_docx_template

# from myutils import logger
ALLOWED_EXTENSIONS = {"pdf", "docx", "jpeg", "jpg"}
app = Flask(__name__)
CORS(app)


@app.route("/start-test/<doc_id>", methods=['GET'])
def start_test(doc_id):
    """
        1. Find Doc with doc_id in the DB (table name: user_doc), raise error if there are none.
        2. Get file from storage path from the fetched doc from DB.
        3. Extract Text from file.
        4. Call LLM API to generate MCQs from text content.
        5. Stored the fetched MCQs in the DB in relation questions.
        6. Update the doc row in user_doc to update a 'test_generated' flag to true
        Update Statement Format => UPDATE TABLE user_doc SET test_generated = true WHERE doc_id = {doc_id}
    """

    fields = [
        "doc_id",
        "doc_name",
        "user_id",
        "size",
        "doc_type",
        "status",
        "subject",
        "grade",
        "timestamp",
        "cloud_url"
    ]

    # SQL Injection
    query = f"""SELECT {", ".join(fields)} FROM public.user_doc WHERE doc_id={doc_id}"""
    result = run_select(query, ())

    if not result:
        return {
            'error': "Invalid doc_id"
        }, 404

    doc_row = result[0]
    print("DB Row Fetched", doc_row)

    doc = make_dict(fields, doc_row)

    print("Doc", doc)

    filename = doc.get('doc_name')
    local_path = get_file_path(filename)

    text = None
    doc_type = doc.get('doc_type')

    if doc_type == "application/pdf":
        text = extract_text_from_pdf(local_path)

    elif doc_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        text = get_docx_text(local_path)

    # Call MCQ-Generator API
    res = generate_mcqs(text)

    query = """INSERT INTO public.questions(doc_id, question, options, explanation, ref)
                   VALUES(%s, %s, %s, %s, %s) RETURNING id"""

    for mcq in res["questions"]:
        _res = run_select(query, (doc_id, mcq['question'], json.dumps(mcq['options']),
                                  mcq['explanation'], mcq['ref']))
        print("RES", _res)

    query1 = f"""UPDATE user_doc SET test_generated = true WHERE doc_id = {doc_id}"""
    result = exec_query(query1)
    print(result)

    return text


@app.route("/question-list/<doc_id>", methods=["GET"])
def question_list(doc_id):

    # doc_id = request.args.get("doc_id")
    fields = [
        "id",
        "doc_id",
        "question",
        "options",
        "explanation",
        "ref"

    ]
    s_fields = ",".join(fields)
    # query = f"""select doc_id,questions,options,explanation,ref from public.questions"""
    query = f"""select {s_fields} from public.questions where doc_id={doc_id}"""
    result = run_select(query)
    print(result)
    fields2 = [fields_as(field) for field in fields]
    print(fields2)
    d = [make_dict(fields2, row) for row in result]
    print(d)

    return json.dumps({"questions": d})  # json.dumps(d

@app.route("/docs", methods=["GET"])
def doc_list():
    """
    for given user, return uploaded documents
    """
    user_id = request.args.get("user_id")
    fields = [
        "doc_id as id",
        "doc_name",
        "user_id",
        "size",
        "doc_type",
        "status",
        "subject",
        "grade",
        "test_generated",
        "TO_CHAR(timestamp, 'YYYY-MM-DD') as date",
        "cloud_url"
    ]
    s_fields = ",".join(fields)
    query = f"""select {s_fields} from public.user_doc where doc_type IS NOT NULL ORDER BY doc_id DESC"""
    result = run_select(query, (user_id,))
    fields2 = [fields_as(field) for field in fields]
    print(fields2)
    d = [make_dict(fields2, row) for row in result]
    doc_type = [row[3] for row in result if row[3]]

    if doc_type:
        list_set = sorted(set(doc_type))
        # convert the set to the list
        doc_type = (list(list_set))
    doc_type = ['Resume', 'Lease-Agreement']
    print(doc_type)
    return json.dumps({"file_list": d, "doc_type": doc_type})  # json.dumps(d)


def doc_status_helper(doc_id):
    fields = [
        "doc_id",
        "doc_name",
        "user_id",
        "size",
        "doc_type",
        "page_count",
        "status",
        "cloud_url",
        "substring(cast(ts_upload as text), 1, 19) as ts_upload",
    ]
    s_fields = ",".join(fields)
    query = f"""select {s_fields} from public.user_doc where doc_id=%s"""
    result = run_select(query, (doc_id,))
    fields2 = [fields_as(field) for field in fields]
    d = make_dict(fields2, result[0]) if result else {}
    return d


@app.route("/doc/status", methods=["GET"])
def doc_status():
    """
    for given user, return uploaded documents
    """
    doc_id = request.args.get("doc_id")
    d = doc_status_helper(doc_id)
    return json.dumps(d)


@app.route("/doc/text", methods=["GET"])
def doc_text():
    """
    for given user, return uploaded documents
    """
    doc_id = request.args.get("doc_id")
    fields = ["a.doc_text as raw_text", "b.doc_text as standard_text"]
    # s_fields = ",".join(fields)
    # Jan-5
    # query = f"""select {s_fields} from dcompare.doc_text a inner join dcompare.doc_text b
    # on a.doc_id=b.doc_id
    # where a.doc_id=%s
    # and a.text_type='raw' and b.text_type='standard'
    # """

    # modified
    query = f"""select text_type, doc_text from dcompare.doc_text where dcompare.doc_text.doc_id=%s"""
    result = run_select(query, (doc_id,))

    if result:
        fields2 = [fields_as(field) for field in fields]
        d = make_dict(fields2, result[0]) if result else {}
        d["raw_text"] = d["raw_text"].replace("\n", "<br>")
        d["standard_text"] = d["standard_text"].replace("\n", "<br>")

        # modified Jan-5
        d = []
        text_type = []
        doc_text = []
        for field in result:
            data = {}
            data["text_type"] = field[0].replace("\n", "<br>")
            data["doc_text"] = field[1].replace("\n", "<br>")

            text_type.append(
                {'option_text': data["text_type"], 'option_value': data["text_type"]})
            doc_text.append(data)
        d = {'text_type': text_type, 'doc_text': doc_text}
    else:
        d = {}

    return json.dumps(d)


def doc_text_get(doc_id, text_type):
    query = f"""select doc_text from dcompare.doc_text
    where doc_id=%s and text_type=%s
    """
    result = run_select(query, (doc_id, text_type))
    return result[0][0] if result else None


@app.route("/doc/compare", methods=["GET"])
def doc_compare_headings():
    doc_id1 = request.args.get("doc_id1")
    doc_id2 = request.args.get("doc_id2")
    text_type = request.args.get("text_type")
    # text type can be summary or standard

    text1 = doc_text_get(doc_id1, text_type)
    text2 = doc_text_get(doc_id2, text_type)

    return json.dumps(
        {
            "diff": table_diff_in_html(
                text1.split("\n"), text2.split("\n"), "left", "right"
            )
        }
    )


def makeres(status, s, code):
    return {"status": status, "msg": s}, code, {'Content-Type': 'application/json'}


UPLOAD_FOLDER = 'local_uploads'
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'jpeg', 'jpg'}


def get_file_path(filename):
    return os.path.join(UPLOAD_FOLDER, filename)

@app.route("/doc-upload", methods=["POST"])
def doc_upload():
    try:
        if 'file' not in request.files:
            return makeres("error", "file not present in request", 400)

        file = request.files['file']
        if file.filename == '':
            return makeres("error", "no selected file", 400)

        lname = file.filename.lower()

        if not (lname.endswith(".pdf") or lname.endswith(".docx") or lname.endswith(".jpeg") or lname.endswith(".jpg")):
            return makeres("error", "only pdf, docx, jpeg, and jpg are supported", 400)

        # Determine content type
        content_type = (
            {"content_type": "application/pdf"} if lname.endswith(".pdf") else
            {"content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"} if lname.endswith(".docx") else
            {"content_type": "image/jpeg"} if lname.endswith(
                ".jpeg") or lname.endswith(".jpg") else None
        )

        # Secure filename
        filename = secure_filename(file.filename)

        # Create directory if it does not exist
        if not os.path.exists(UPLOAD_FOLDER):
            os.makedirs(UPLOAD_FOLDER)

        # Save file locally
        local_path = get_file_path(filename)
        file.save(local_path)

        user_id = request.args.get("user_id")
        doc_type = request.form.get("doc_type")
        subject = request.form.get("subject")
        grade = request.form.get("grade")

        query = """SELECT doc_name FROM public.user_doc WHERE user_id=%s AND doc_name=%s"""
        result = run_select(query, (user_id, filename))

        if result:
            return makeres("error", f"{filename} exists already. Rename and try again", 417)

        file_data = file.read()
        sz = -1

        # Upload the file to Azure Blob Storage
        # res = upload_file_to_cloud(file_data, filename, content_type)
        # cloud_path = res.get("url", "")

        query = """INSERT INTO public.user_doc(doc_name, user_id, size, doc_type, subject, grade, cloud_url, status)
                   VALUES(%s, %s, %s, %s, %s, %s, %s, %s) RETURNING doc_id"""
        result = run_select(query, (filename, user_id, sz,
                            doc_type, subject, grade, 'cloud_path', "uploaded"))

        doc_id = None
        if len(result) > 0:
            doc_ids = result[0]
            if len(doc_ids) > 0:
                doc_id = doc_ids[0]

        return makeres("ok", f"{filename} uploaded", 200)
    except Exception as e:
        logging.error(e)
        return makeres("error", str(e), 503)


def makeres(status, message, status_code):
    return make_response({"status": status, "message": message}, status_code)


# @app.route("/doc/text-extract", methods=["GET"])
# def text_extract():
#     try:
#         doc_id = request.args.get("doc_id")
#         return text_extract_helper(doc_id)
#     except Exception as e:
#         return makeres("error", str(e), 503)

@app.route('/doc/text-extract', methods=['GET'])
def extract_text():
    doc_id = request.args.get('doc_id')

    try:
        doc_id = request.args.get("doc_id")
        return text_extract_helper(doc_id)
    except Exception as e:
        return makeres("error", str(e), 503)


def update_text(fname, docid, doctype):
    with open(fname, "r") as f:
        s = f.read()
        update_table_fields(
            "doc_text",
            ["doc_text"],
            [s],
            "where doc_id=%s and text_type=%s",
            [docid, doctype],
        )


"""Separate the sections in the text """


@app.route("/ocr", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify(error="No file part in the request"), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify(error="No selected file"), 400

    filename = secure_filename(file.filename)
    file_extension = os.path.splitext(filename)[1]
    if file_extension == ".docx":
        separated_english_texts = extract_text_from_docx(file)
        return jsonify(data=separated_english_texts)

    elif file_extension == ".pdf":
        Extract_pdf(file)

    return jsonify(extension=file_extension), 200


# new function to save edited text
def post_save_text(docid, doctype, data):
    if doctype != " ":
        s = data
        update_table_fields(
            "doc_text",
            ["doc_text"],
            [s],
            "where doc_id=%s and text_type=%s",
            [docid, doctype],
        )


# new function, to remove HTML tags
def on_changed_body(target, value, oldvalue, initiator=None):
    allowed_tags = ['a', 'abbr', 'acronym', 'b', 'blockquote', 'code',
                    'em', 'i', 'li', 'ol', 'pre', 'strong', 'ul',
                    'h1', 'h2', 'h3', 'br']  # , 'p'
    target = bleach.linkify(bleach.clean(
        markdown(value, output_format='html'), tags=allowed_tags, strip=True))
    return bleach.linkify(bleach.clean(markdown(value, output_format='html'), tags=allowed_tags, strip=True))


@app.route("/savetext", methods=["POST"])
@cross_origin()
def doc_save_text():
    try:
        req = request.get_json()
        print(req['file_id'])
        print(req['filename'])
        # data = "\n".join(req['data'])

        req['data'] = req['data'].replace("<p>&nbsp;</p>", "<br>")
        req['data'] = req['data'].replace("<br>", "\n")
        req['data'] = req['data'].replace("&nbsp;", "")

        data = on_changed_body("doc_text", req['data'], req['data'])
        post_save_text(req['file_id'], "standard", data)
        print("data \n", data)
        return jsonify(req), 200
    except Exception as e:
        return makeres("error", str(e), 503)


@app.route("/doc-download", methods=["GET", "POST"])
def fill_and_download():
    errcode = 201
    try:
        doc_type = request.args.get("doc_type")
        doc_id = request.args.get("file_id")

        template_id = request.args.get("template_id")
        template_id = int(template_id) if template_id else None
        d = doc_status_helper(doc_id) if doc_id else None
        # download as-is file
        if template_id <= 0:
            directory_name = 'abc'
            file_path = directory_name + '/' + d['doc_name']
            download_from_cloud(d['doc_name'], directory_name)
            return send_file(file_path, as_attachment=True)
        d1 = ''
        new_name = ''
        if d:
            user_id = d['user_id']
            uuid = uuid1()
            folderName = 'tmp'
            new_name = f'{folderName}/{user_id}-{uuid}.docx'
            d1 = doc_status_helper(template_id) if template_id else None
            create_folder_not_exist(folderName)
        if template_id > 0 and doc_type == "Resume":
            if d1:
                json_txt = doc_text_get(doc_id, 'v1-interim')
                if not json_txt:
                    return makeres('error', f'document json not present', errcode)

                template_name = d1['doc_name']
                # status_code = fill_docx_template(template_name, json.loads(json_txt), new_name)
                # if status_code == 200:
                #     return send_file(new_name, as_attachment=True)
                # else:
                #     return makeres('error', f'status_code={status_code}', errcode)
        elif template_id > 0 and doc_type == "Lease-Agreement":
            if d1:
                json_data = doc_text_get(doc_id, 'v2-interim')
                if not json_data:
                    return makeres('error', f'document json not present', errcode)
                template_name = d1['doc_name']
                status_code = update_lease_agreement_with_template(
                    json_data, template_name, new_name)
                if status_code == 200:
                    return send_file(new_name, as_attachment=True)
                else:
                    return makeres('error', f'status_code={status_code}', errcode)
    except FileNotFoundError as file_not_found:
        return makeres("error", "file does not exist", 404)
    except Exception as e:
        return makeres("error", str(e), 500)


@app.route("/search", methods=["POST"])
def doc_search():
    try:
        req = request.get_json()
        doc_type = req['doc_type']
        if doc_type.strip() is None:
            return response("error", "doctype should not be None", [], 400)
        elif doc_type == "Resume":
            resp = get_file_name_with_id(
                req["message"], RESUME_ASSISTANCE_ID, doc_type)
        elif doc_type == "Lease-Agreement":
            resp = get_file_name_with_id(
                req["message"], LEASE_ASSISTANCE_ID, doc_type)
        elif doc_type == "Email":
            resp = get_file_name_with_id(
                req["message"], EMAIL_ASSISTANCE_ID, doc_type)
        else:
            return response("error", "Invalid doctype", [], 400)
        if resp is None or isinstance(resp, dict):
            return response("success", "Records are not found", [], 200)
        return response("success", "Data fetch  successfully", resp, 200)
    except Exception as e:
        return response("error", str(e), [], 500)


@app.route("/email/email-download", methods=["GET"])
@cross_origin()
def email_download():
    try:
        filename = request.args.get("filename")
        return send_file("email-parser/"+filename, as_attachment=True)
    except FileNotFoundError as file_not_found:
        return makeres("error", "file does not exist", 404)
    except Exception as e:
        return makeres("error", str(e), 503)


@app.route("/resume-download", methods=["GET", "POST"])
def resume_download():
    try:
        # req = request.get_json()
        file_name = request.args.get("file_name")  # req["file_id"]
        template_id = 0
        # import time
        # time.sleep(3)

        if (file_name):
            # "./file-sample_100kB.doc" # 'file-sample_1MB.doc'# './sample.pdf'
            filename = "./" + file_name
            # filename= './sample.pdf'
            # 'application/pdf'
            mimeType = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            # mimeType = 'application/pdf'
            print("filename \n", filename)
            return send_file(filename, as_attachment=True)

    except Exception as e:
        return makeres("error", str(e), 503)


@app.route("/resume/email-parser", methods=["GET", "POST"])
@cross_origin()
def email_parser():
    try:
        resume_categories_dict = fetch_emails_and_categorize()
        return response("success", "Emails parsed successfully", resume_categories_dict, 200)
    except Exception as e:
        return response("error",  str(e), [], 500)


@app.route("/download/<report_name>", methods=["GET", "POST"])
def download(report_name):
    try:
        filename = f"./{report_name}"
        # 'application/pdf'
        mimeType = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        # mimeType = 'application/pdf'
        print("filename \n", filename)
        return send_file(filename, mimetype=mimeType, as_attachment=True)

    except Exception as e:
        return makeres("error", str(e), 503)


# @app.route("/doc-delete/<doc_id>", methods=["DELETE"])
# @cross_origin()
# def doc_delete(doc_id):
#     try:
#         if not doc_id.strip():
#             return makeres("invalid data", "doc_id is required", 400)
#         delete_record("delete from {}.doc_text where doc_id =%s", doc_id)
#         user_doc_deleted_record = delete_record("delete from {}.user_doc where doc_id =%s", doc_id)
#         if user_doc_deleted_record <= 0:
#             return makeres("error", "records are not found", 400)
#         return makeres("success", "deleted successfully", 200)
#     except Exception as e:
#         return makeres("error", str(e), 500)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
