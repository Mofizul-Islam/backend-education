from fpdf import FPDF

# Sample test paper data
test_paper = {
    "title": "10th Grade Science Sample Test Paper",
    "questions": [
        {
            "question": "1. Explain the process of photosynthesis. Include the chemical equation.",
            "marks": "5 marks"
        },
        {
            "question": "2. Describe Newton's three laws of motion with examples.",
            "marks": "6 marks"
        },
        {
            "question": "3. What is the structure of an atom? Explain the role of protons, neutrons, and electrons.",
            "marks": "5 marks"
        },
        {
            "question": "4. Define and differentiate between mitosis and meiosis.",
            "marks": "5 marks"
        },
        {
            "question": "5. Explain the water cycle and its importance to the ecosystem.",
            "marks": "4 marks"
        },
        {
            "question": "6. What are the different types of chemical reactions? Provide examples for each type.",
            "marks": "6 marks"
        },
        {
            "question": "7. Discuss the significance of the periodic table in chemistry.",
            "marks": "4 marks"
        },
        {
            "question": "8. What are renewable and non-renewable energy sources? Give examples.",
            "marks": "5 marks"
        },
        {
            "question": "9. Describe the process of evolution and the evidence that supports it.",
            "marks": "6 marks"
        },
        {
            "question": "10. Explain the concept of plate tectonics and its role in shaping Earth's surface.",
            "marks": "4 marks"
        }
    ]
}

# Create PDF document
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, test_paper['title'], ln=True, align='C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

    def add_questions(self, questions):
        self.set_font('Arial', '', 12)
        for question in questions:
            self.multi_cell(0, 10, question['question'])
            self.ln(1)
            self.set_font('Arial', 'I', 10)
            self.cell(0, 10, question['marks'], ln=True)
            self.set_font('Arial', '', 12)
            self.ln(5)

# Create PDF instance and add a page
pdf = PDF()
pdf.add_page()

# Add questions to the PDF
pdf.add_questions(test_paper['questions'])

# Save the PDF to a file
pdf_file = "10th_grade_science_sample_test_paper.pdf"
pdf.output(pdf_file)

print(f"PDF generated successfully: {pdf_file}")
