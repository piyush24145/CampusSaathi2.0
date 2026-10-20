import os
import pymupdf

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sample_college_notices")
os.makedirs(OUTPUT_DIR, exist_ok=True)

def create_exam_notice():
    doc = pymupdf.open()
    # Page 1
    page1 = doc.new_page()
    page1.insert_text((50, 60), "APEX INSTITUTE OF TECHNOLOGY - OFFICE OF CONTROLLER OF EXAMINATIONS", fontsize=12, fontname="hebo")
    page1.insert_text((50, 80), "Ref No: AIT/COE/2026/NOT-842                                  Date: 15 October 2026", fontsize=9, fontname="helv")
    page1.insert_text((50, 110), "OFFICIAL NOTICE: END-SEMESTER EXAMINATIONS NOVEMBER-DECEMBER 2026", fontsize=13, fontname="hebo")
    
    body1 = """
All students of B.Tech (Semesters 5 and 7) and MCA (Semester 3) are hereby notified that the End-Semester Theory & Practical Examinations for Autumn Session 2026 will commence from 18 November 2026 and conclude on 04 December 2026.

1. Examination Registration & Fee:
- The standard examination registration portal will remain open from 20 October 2026 to 05 November 2026.
- The regular examination fee is Rs 1,500 per semester.
- Late registration with a penalty fee of Rs 500 will be permitted until 09 November 2026 (5:00 PM). No registration requests will be entertained thereafter.

2. Hall Tickets / Admit Cards:
- Digital Admit Cards will be available for download on the student ERP portal from 10 November 2026 onwards.
- Carrying a printed color copy of the Admit Card along with the official Institute Student ID card is strictly mandatory for entry into the examination hall.

3. Attendance Eligibility Criteria:
- As per university academic regulations, a minimum of 75% aggregate attendance in each registered theory and lab course is compulsory to be eligible for writing the semester examinations.
"""
    page1.insert_text((50, 140), body1.strip(), fontsize=10, fontname="helv")

    # Page 2
    page2 = doc.new_page()
    page2.insert_text((50, 60), "APEX INSTITUTE OF TECHNOLOGY - EXAMINATION GUIDELINES (Page 2)", fontsize=11, fontname="hebo")
    body2 = """
4. Exam Timing & Shifts:
- Morning Shift: 09:30 AM to 12:30 PM (Reporting time: 09:00 AM).
- Afternoon Shift: 02:00 PM to 05:00 PM (Reporting time: 01:30 PM).
- Students arriving more than 15 minutes after the commencement of the exam will not be permitted inside the examination hall.

5. Prohibited Items:
- Mobile phones, smartwatches, programmable calculators, Bluetooth devices, and loose paper sheets are strictly prohibited inside the exam hall. Possession of any electronic gadget will be treated as Unfair Means (UFM).

6. Contact & Grievance:
- In case of discrepancies in subject codes or admit cards, email: exam@college.edu or visit the COE Cell, Room 204, Administrative Block.

(Dr. R. K. Sharma)
Controller of Examinations
Apex Institute of Technology
"""
    page2.insert_text((50, 90), body2.strip(), fontsize=10, fontname="helv")
    
    file_path = os.path.join(OUTPUT_DIR, "Notice_Exam_Schedule_2026.pdf")
    doc.save(file_path)
    doc.close()
    print(f"Created: {file_path}")

def create_hostel_notice():
    doc = pymupdf.open()
    page1 = doc.new_page()
    page1.insert_text((50, 60), "APEX INSTITUTE OF TECHNOLOGY - COUNCIL OF WARDENS", fontsize=12, fontname="hebo")
    page1.insert_text((50, 80), "Ref No: AIT/CW/HOSTEL/2026/089                                Date: 12 October 2026", fontsize=9, fontname="helv")
    page1.insert_text((50, 110), "HOSTEL RE-ALLOTMENT AND FEE NOTIFICATION FOR ODD SEMESTER 2026", fontsize=13, fontname="hebo")

    body = """
This notice is issued for all returning and newly admitted hostel residents for Boys Hostels (Aryabhata, Raman) and Girls Hostels (Kalpana, Gargi).

1. Allotment Schedule & Check-in:
- Room occupancy and key distribution will be carried out between 01 November 2026 and 03 November 2026 from 10:00 AM to 5:00 PM.
- Residents must produce their semester fee receipt and hostel clearance slip at the warden office counter.

2. Hostel Fee Structure:
- Accommodation & Maintenance Fee: Rs 24,000 per semester.
- Mess Advance (inclusive of breakfast, lunch, snacks, and dinner): Rs 18,000 per semester.
- Total Hostel Fee payable: Rs 42,000 per semester.
- The last date to pay hostel fees without late fine is 28 October 2026 via SBI Collect / College ERP.

3. Hostel Timings & Rules:
- The main entry gate of all hostels will be locked strictly at 09:30 PM every night.
- Overnight leave / night-out passes must be applied on the ERP portal at least 24 hours in advance and verified by parents' phone call.
- Cooking appliances, electric heaters, and iron presses are strictly prohibited inside hostel rooms due to fire safety regulations. Violation will result in a penalty of Rs 2,500.

4. Chief Warden Office Contact:
- Email: hostel@college.edu
- Chief Warden Office: Block B, Room 102 (Timings: 4:00 PM to 6:00 PM on weekdays).
- Emergency Medical Helpline: +91-9876543210 (Available 24x7).

Chief Warden, Council of Wardens
"""
    page1.insert_text((50, 140), body.strip(), fontsize=10, fontname="helv")
    
    file_path = os.path.join(OUTPUT_DIR, "Notice_Hostel_Allotment_Rules_2026.pdf")
    doc.save(file_path)
    doc.close()
    print(f"Created: {file_path}")

def create_library_notice():
    doc = pymupdf.open()
    page1 = doc.new_page()
    page1.insert_text((50, 60), "APEX INSTITUTE OF TECHNOLOGY - CENTRAL LIBRARY", fontsize=12, fontname="hebo")
    page1.insert_text((50, 80), "Circular No: AIT/LIB/CIR/2026/19                               Date: 05 October 2026", fontsize=9, fontname="helv")
    page1.insert_text((50, 110), "CENTRAL LIBRARY TIMINGS, RULES & DIGITAL ACCESS GUIDELINES", fontsize=13, fontname="hebo")

    body = """
All students, research scholars, and faculty members are requested to take note of the operational schedule and policies of the Central Library.

1. Library Timings:
- Main Stack and Circulation Counter: Monday to Friday: 09:00 AM to 07:00 PM. Saturday: 10:00 AM to 04:00 PM.
- Air-Conditioned Central Reading Hall: 08:00 AM to 11:00 PM daily (including Saturdays and Sundays during exam periods).
- Digital e-Resource Center: 09:00 AM to 08:00 PM on working days.

2. Book Borrowing Privileges & Renewal:
- Undergraduate (B.Tech) Students: 4 books for a period of 14 days.
- Postgraduate (M.Tech/MCA) Students: 6 books for a period of 28 days.
- Books can be reissued online once through the OPAC portal if no hold has been placed by another borrower.

3. Overdue Fines & Lost Book Policy:
- An overdue fine of Rs 5 per day per book will be charged automatically on delayed returns.
- In case of loss or severe damage of a library book, the borrower must replace it with the latest edition or pay twice the purchase cost of the book.

4. E-Library & Online Database Access:
- Institutional IEEE Xplore, ScienceDirect, and SpringerLink portals are accessible via campus Wi-Fi or remotely via VPN: https://elibrary.college.edu.
- For library membership cards or RFID card activation, contact librarian@college.edu or Room 101, Ground Floor, Central Library.

Chief Librarian
Central Library, Apex Institute of Technology
"""
    page1.insert_text((50, 140), body.strip(), fontsize=10, fontname="helv")
    
    file_path = os.path.join(OUTPUT_DIR, "Notice_Library_Guidelines_Timings.pdf")
    doc.save(file_path)
    doc.close()
    print(f"Created: {file_path}")

if __name__ == "__main__":
    create_exam_notice()
    create_hostel_notice()
    create_library_notice()
    print("All sample notice PDFs created successfully.")
