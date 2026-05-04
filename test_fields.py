import os
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from pdf_filler import fill_pdf_with_overlay

def create_dummy_template(num_pages=10):
    """Create a basic blank PDF with some text if no template is found."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    for i in range(num_pages):
        c.drawString(50, 800, f"-- Dummy Template Page {i+1} --")
        # Draw a grid or rulers to help visualize coordinates
        c.setStrokeColorRGB(0.8, 0.8, 0.8)
        for y in range(0, 842, 50):
            c.line(0, y, 595, y)
            c.setFont("Helvetica", 6)
            c.drawString(10, y + 2, f"y={y}")
        for x in range(0, 595, 50):
            c.line(x, 0, x, 842)
            c.drawString(x + 2, 10, f"x={x}")
            
        c.showPage()
    c.save()
    buf.seek(0)
    return buf.read()

def main():
    template_path = "ojt_template.pdf"
    
    if os.path.exists(template_path):
        print(f"Using existing template: {template_path}")
        with open(template_path, "rb") as f:
            pdf_bytes = f.read()
    else:
        print("Template not found. Creating a dummy 10-page template with gridlines.")
        pdf_bytes = create_dummy_template()

    # Dummy User Details for Page 3 (Index 2)
    user_details = {
        "name": "Jane Smith",
        "registration_number": "REG-987654321",
        "start_date": "2024-06-01",
        "program_name": "B.S. Information Technology",
        "semester": "8th Semester",
        "location": "San Francisco, CA",
        "industry_partner_name": "Tech Corp Innovators",
        "phone_no": "+1 (555) 123-4567",
        "email_id": "janesmith@example.com"
    }

    # Dummy Journal Entries (these should start appearing from Page 8, Index 7)
    pages_data = [
        {
            "date": "2024-06-03",
            "ojt_timing": "9:00 AM - 5:00 PM",
            "department": "Engineering",
            "designation": "Intern",
            "my_space": "Felt good about the first day.",
            "tasks_carried_out": "Set up development environment.\nMet the team.\nRead project docs.",
            "key_learnings": "Learned about the company stack.",
            "tools_used": "Git, Docker, VS Code",
            "special_achievements": "Successfully completed onboarding."
        },
        {
            "date": "2024-06-04",
            "ojt_timing": "9:00 AM - 5:00 PM",
            "department": "Engineering",
            "designation": "Intern",
            "my_space": "A bit overwhelmed but learning.",
            "tasks_carried_out": "Fixed a minor bug.\nWrote unit tests.",
            "key_learnings": "Jest testing framework.",
            "tools_used": "Jest, Node.js",
            "special_achievements": "First merged PR!"
        }
    ]

    print("Generating test PDF...")
    output_bytes = fill_pdf_with_overlay(pdf_bytes, pages_data, user_details)
    
    output_filename = "test_layout_output.pdf"
    with open(output_filename, "wb") as f:
        f.write(output_bytes)
        
    print(f"Done! Open '{output_filename}' to review the positions.")

if __name__ == "__main__":
    main()
