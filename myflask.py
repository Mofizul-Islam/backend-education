
import asyncio
import json
import os
import bcrypt
# import services.mcq_generator
# services.mcq_generator.generate_mcqs()
from services.mcq_generator import generate_mcqs, generate_questions, MCQ
import bleach
from datetime import date
from flask import request, make_response
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS, cross_origin
from markdown import markdown
from werkzeug.utils import secure_filename
from uuid import uuid1
import logging
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
# from aihelper import get_file_name_with_id, get_resume_categories
from mydb import exec_query, run_select, update_table_fields
# from flask_mysqldb import MySQL
# import MySQLdb.cursors
from myutils import (
    DB_SCHEMA,
    PORT,
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
import db.mysql
import logging

logging.basicConfig(filename="logs.log", filemode="w",
                    format="%(name)s → %(levelname)s: %(message)s")

logging.debug(f"ENVIRON: {str(os.environ)}")

# from ocr import extract_text_from_docx, Extract_pdf
# from workhorse import test5, delete_record
# from externals import fill_docx_template

# from myutils import logger
ALLOWED_EXTENSIONS = {"pdf", "docx", "jpeg", "jpg"}
app = Flask(__name__)

app.config["JWT_SECRET_KEY"] = "super-secret"  # Change this!
jwt = JWTManager(app)
CORS(app)
# db.mysql.init(app)


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

    today_date = date.today()
    test_name = request.args.get("test_name")
    mcq_count = request.args.get("mcq_count")
    shortques_count = request.args.get("shortques_count")
    longques_count = request.args.get("longques_count")
    if not test_name:
        return makeres("error", "test_name is not present", 400)

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
    # print("DB Row Fetched", doc_row)

    doc = make_dict(fields, doc_row)

    # print("Doc", doc)

    filename = doc.get('doc_name')
    local_path = get_file_path(filename)

    text = None
    doc_type = doc.get('doc_type')

    if doc_type == "application/pdf":
        text = extract_text_from_pdf(local_path)

    elif doc_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        text = get_docx_text(local_path)

    # Call MCQ-Generator API
    res = asyncio.run(generate_questions(text, {
        'long_question': longques_count,
        'short_question': shortques_count,
        'mcq': mcq_count
    }))

    query = """INSERT INTO public.question_test(generated_date, type, test, doc_id)
                VALUES(%s, %s, %s, %s) RETURNING id"""

    test_res = exec_query(
        query, (
            today_date.strftime("%Y-%m-%d"),
            "pdf",
            test_name,
            doc_id
        ),
        True
    )

    if not test_res:
        return makeres("error", "could not create test", 500)

    test_id = test_res[0][0]

    query = """INSERT INTO public.questions(doc_id, question, answer, options, explanation, ref, type, test_id)
                VALUES(%s, %s, %s, %s, %s, %s, %s,%s) RETURNING id"""

    print(res)
    res_dict_arr = []
    for question in res:
        res_dict_arr.append(question.model_dump())
        exec_query(
            query, (
                doc_id,
                question.question,
                question.answer,
                json.dumps(question.options) if isinstance(
                    question, MCQ) else None,
                question.explanation,
                question.ref,
                question.type,
                test_id,
            )
        )

    # query1 = f"""UPDATE user_doc SET test_generated = true WHERE doc_id = {doc_id}"""
    # result = exec_query(query1)
    # print(result)

    return jsonify({
        'status': 'success',
        'test_id': test_id,
        "questions": res_dict_arr
    }), 201


@app.route("/question-test/<doc_id>", methods=["GET"])
@app.route("/question-test", methods=["GET"])
def question_test(doc_id=None):

    fields = [
        "id",
        "TO_CHAR(generated_date, 'YYYY-MM-DD') as generated_date",
        "type",
        "test",
        "question_test.doc_id as doc_id",
        "grade",
        "subject"
    ]

    t_fields = ','.join(fields)
    query = f"""select {t_fields} from public.question_test INNER JOIN user_doc ON question_test.doc_id= user_doc.doc_id"""
    if doc_id:
        query += f" where question_test.doc_id={doc_id}"

    print(query)
    t_result = run_select(query)
    print(t_result)
    fields3 = [fields_as(field) for field in fields]
    print(fields3)
    t = [make_dict(fields3, row) for row in t_result]
    print(t)

    return jsonify({"test_questions": t})


@app.route("/question-list/<test_id>", methods=["GET"])
def question_list(test_id):

    # doc_id = request.args.get("doc_id")
    fields = [
        "id",
        "doc_id",
        "type",
        "question",
        "answer",
        "options",
        "explanation",
        "ref"

    ]
    s_fields = ",".join(fields)
    # query = f"""select doc_id, type,questions, answer,options,explanation,ref from public.questions"""
    query = f"""select {s_fields} from public.questions where test_id={test_id}"""
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
    logging.debug(f"Get Docs: {user_id} {query}")
    print(f"Get Docs: {user_id} {query}")

    result = run_select(query, (user_id,))
    # result = db.mysql.fetch_all(query, (user_id,))
    # d = result
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
    # return json.dumps({"file_list": d})  # json.dumps(d)


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


# def makeres(status, message, status_code):
#     return make_response({"status": status, "message": message}, status_code)


# @app.route("/doc/text-extract", methods=["GET"])
# def text_extract():
#     try:
#         doc_id = request.args.get("doc_id")
#         return text_extract_helper(doc_id)
#     except Exception as e:
#         return makeres("error", str(e), 503)

# @app.route('/doc/text-extract', methods=['GET'])
# def extract_text():
#     doc_id = request.args.get('doc_id')

#     try:
#         doc_id = request.args.get("doc_id")
#         return text_extract_helper(doc_id)
#     except Exception as e:
#         return makeres("error", str(e), 503)


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


# @app.route("/ocr", methods=["POST"])
# def upload_file():
#     if "file" not in request.files:
#         return jsonify(error="No file part in the request"), 400

#     file = request.files["file"]

#     if file.filename == "":
#         return jsonify(error="No selected file"), 400

#     filename = secure_filename(file.filename)
#     file_extension = os.path.splitext(filename)[1]
#     if file_extension == ".docx":
#         separated_english_texts = extract_text_from_docx(file)
#         return jsonify(data=separated_english_texts)

#     elif file_extension == ".pdf":
#         Extract_pdf(file)

#     return jsonify(extension=file_extension), 200


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


# @app.route("/search", methods=["POST"])
# def doc_search():
#     try:
#         req = request.get_json()
#         doc_type = req['doc_type']
#         if doc_type.strip() is None:
#             return response("error", "doctype should not be None", [], 400)
#         elif doc_type == "Resume":
#             resp = get_file_name_with_id(
#                 req["message"], RESUME_ASSISTANCE_ID, doc_type)
#         elif doc_type == "Lease-Agreement":
#             resp = get_file_name_with_id(
#                 req["message"], LEASE_ASSISTANCE_ID, doc_type)
#         elif doc_type == "Email":
#             resp = get_file_name_with_id(
#                 req["message"], EMAIL_ASSISTANCE_ID, doc_type)
#         else:
#             return response("error", "Invalid doctype", [], 400)
#         if resp is None or isinstance(resp, dict):
#             return response("success", "Records are not found", [], 200)
#         return response("success", "Data fetch  successfully", resp, 200)
#     except Exception as e:
#         return response("error", str(e), [], 500)


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


@app.route('/signup', methods=['POST'])
def signup():
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')

        if not email or not password:
            return makeres("error", "All fields are required", 400)

        hashed_password = bcrypt.hashpw(
            password.encode('utf-8'), bcrypt.gensalt())

        query = """INSERT INTO users (email, password) VALUES (%s, %s) RETURNING email"""
        result = exec_query(
            query, (email, hashed_password.decode('utf-8')), True)
        if not result:
            return makeres("error", "Invalid email or password", 401)

        return makeres("success", "User created successfully", 201)
    except Exception as e:
        logging.error(e)
        print("error", e)
        return makeres("error", str(e), 500)


@app.route('/signin', methods=['POST'])
def signin():
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')

        if not email or not password:
            return make_response({"error": "All fields are required"}, 400)

        query = """SELECT id, password FROM users WHERE email = %s"""
        result = run_select(query, (email,))
        # [
        #     [1, 'hashedPassword'],
        #     [],
        #     []
        # ]

        if not result:
            return make_response({"error": "Invalid email or password"}, 401)

        user_id, hashed_password = result[0]
        # user_id = result[0][0]
        # hashed_password = result[0][1]

        if bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8')):
            access_token = create_access_token(
                identity={'user_id': user_id, 'email': email})
            return make_response({"access_token": access_token, "status": "success", "user": {"email": email}}, 200)

        return make_response({"error": "Invalid email or password"}, 401)
    except Exception as e:
        return make_response({"error": str(e)}, 500)


@app.route('/protected', methods=['GET'])
@jwt_required()
def protected():
    current_user = get_jwt_identity()
    return make_response({"message": f"Hello, {current_user}!"}, 200)


@app.route('/user-profile', methods=["GET"])
@jwt_required()
def get_user_profile():
    current_user = get_jwt_identity()
    user_id = current_user['user_id']
    print("user-id response", user_id)

    fields = [
        "user_id",
        "first_name",
        "last_name",
        "cell_number",
        "address",
        "city",
        "country",
        "zip_code",
        "qualification",
        "subject",
        "grade",
        "school_name",
        "school_code",
        "experience"

    ]

    s_fields = ",".join(fields)
    query = f"""SELECT {s_fields} FROM public.user_profile WHERE user_id={user_id} """
    result = run_select(query, (user_id,))
    fields2 = [fields_as(field) for field in fields]
    user_profile_dict = make_dict(fields2, result[0]) if result else {}
    return user_profile_dict


@app.route('/user-profile', methods=['Post'])
@jwt_required()
def user_profile():
    current_user = get_jwt_identity()
    user_id = current_user['user_id']
    print("user-id response", user_id)

    fields = [
        "user_id",
        "first_name",
        "last_name",
        "cell_number",
        "address",
        "city",
        "country",
        "zip_code",
        "qualification",
        "subject",
        "grade",
        "school_name",
        "school_code",
        "experience"

    ]

    s_fields = ",".join(fields)
    query = f"""SELECT {s_fields} FROM public.user_profile WHERE user_id={user_id} """
    result = run_select(query, (user_id,))
    fields2 = [fields_as(field) for field in fields]
    user_profile_dict = make_dict(fields2, result[0]) if result else {}
    data = request.get_json()
    # return user_profile_dict

    if len(result) == 0:
        query = """INSERT INTO public.user_profile(
            user_id, first_name, 
            last_name, cell_number, address, city, 
            country, zip_code, qualification, subject, 
            grade, school_name, school_code, experience)
                VALUES(%s, %s, %s, %s, %s, %s, %s, %s,%s, %s, %s, %s, %s, %s) RETURNING user_id"""
        result = run_select(query, (
            user_id,
            data.get("first_name"), data.get("last_name"),
            data.get("cell_number"), data.get("address"),
            data.get("city"), data.get("country"),
            data.get("qualification"), data.get("subject"),
            data.get("zip_code"), data.get("grade"),
            data.get("school_name"), data.get("school_code"),
            data.get("experience")
        )
        )
        if not result:
            return make_response({"message": "Make sure all required fields are provided"}, 400)

    else:
        for col in data:
            user_profile_dict[col] = data[col]

        query1 = """UPDATE user_profile 
                        SET first_name=%(first_name)s, last_name=%(last_name)s,
                        cell_number=%(cell_number)s, address=%(address)s, 
                        city=%(city)s, country=%(country)s, zip_code=%(zip_code)s, 
                        qualification=%(qualification)s, subject=%(subject)s, grade=%(grade)s, 
                        school_name=%(school_name)s,school_code=%(school_code)s,
                        experience=%(experience)s WHERE user_id = %(user_id)s"""
        print("query", query1)
        result = exec_query(query1, user_profile_dict)
        print("result", result)

    return make_response({"message": f"Updated user profile"}, 200)


@app.route("/hello", methods=['GET'])
def hello():
    return make_response({"message": "Hello there"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT or 5000, debug=True)
