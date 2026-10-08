import os
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        
        # Header (Pages > 1)
        if self._pageNumber > 1:
            self.drawString(54, 750, "OSDBMS PBL Project Upgrade & Strategic Roadmap | Team ID: OSDBMS-V-2026-T135")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(54, 742, 558, 742)
            
        # Footer
        footer_right = f"Graphic Era University | OSDBMS Phase-2 | Page {self._pageNumber} of {page_count}"
        self.drawRightString(558, 32, footer_right)
        self.drawString(54, 32, "CONFIDENTIAL - ACADEMIC STRATEGY PLAN")
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(54, 44, 558, 44)
        self.restoreState()

def build_pdf(filename):
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )
    
    styles = getSampleStyleSheet()
    
    # Custom Palette
    PRIMARY = colors.HexColor("#1E3A8A")   # Deep Navy
    SECONDARY = colors.HexColor("#2563EB") # Royal Blue
    ACCENT = colors.HexColor("#059669")    # Emerald Green
    TEXT_DARK = colors.HexColor("#0F172A") # Dark Slate
    BG_LIGHT = colors.HexColor("#F8FAFC")  # Light Gray
    BORDER_COLOR = colors.HexColor("#CBD5E1")

    # Custom Typography Styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Title'],
        fontName='Helvetica-Bold',
        fontSize=22,
        leading=26,
        textColor=PRIMARY,
        alignment=0,
        spaceAfter=6
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=12,
        leading=16,
        textColor=SECONDARY,
        spaceAfter=15
    )
    
    h1_style = ParagraphStyle(
        'Heading1_Custom',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=PRIMARY,
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=SECONDARY,
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=TEXT_DARK,
        spaceAfter=6
    )

    bullet_style = ParagraphStyle(
        'Bullet_Custom',
        parent=body_style,
        leftIndent=12,
        firstLineIndent=-8,
        spaceAfter=4
    )

    callout_style = ParagraphStyle(
        'Callout_Text',
        parent=body_style,
        fontName='Helvetica-Oblique',
        textColor=colors.HexColor("#1E293B"),
        leading=13
    )

    tbl_cell = ParagraphStyle('TblCell', parent=body_style, fontSize=8.5, leading=11, spaceAfter=0)
    tbl_hdr = ParagraphStyle('TblHdr', parent=body_style, fontName='Helvetica-Bold', fontSize=9, leading=12, textColor=colors.white, spaceAfter=0)

    story = []

    # Title Banner
    story.append(Paragraph("OSDBMS Project Enhancement & Integration Strategy", title_style))
    story.append(Paragraph("Transforming Disaster Resource Allocation into an Exemplary OS & DBMS Engineering System", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=PRIMARY, spaceBefore=0, spaceAfter=12))

    # Meta Info Table
    meta_data = [
        [Paragraph("<b>Project Title:</b> Disaster Resource Allocation & Shelter Management", tbl_cell),
         Paragraph("<b>Course:</b> 5th Sem OSDBMS PBL", tbl_cell)],
        [Paragraph("<b>Team ID:</b> OSDBMS-V-2026-T135", tbl_cell),
         Paragraph("<b>Institution:</b> Graphic Era (Deemed to be University)", tbl_cell)],
        [Paragraph("<b>Team Lead:</b> Anushreya Tomar (24022202)", tbl_cell),
         Paragraph("<b>Team Members:</b> Akanchha, Ishani, Simarjeet", tbl_cell)],
        [Paragraph("<b>Mentor:</b> Dr. Ankit Tomar", tbl_cell),
         Paragraph("<b>Target Domain:</b> Systems & DB Kernel Engineering", tbl_cell)]
    ]
    meta_table = Table(meta_data, colWidths=[250, 254])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), BG_LIGHT),
        ('PADDING', (0,0), (-1,-1), 5),
        ('BOX', (0,0), (-1,-1), 1, BORDER_COLOR),
        ('INNERGRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 12))

    # Section 1: Executive Summary & Feedback Diagnosis
    story.append(Paragraph("1. Executive Summary & Mentor Feedback Diagnosis", h1_style))
    story.append(Paragraph(
        "<b>Core Feedback:</b> Evaluators noted that the current project proposal leans heavily towards generic Web Application CRUD (Create, Read, Update, Delete) with insufficient demonstration of core Operating System and Database Management System engineering concepts.",
        body_style
    ))
    story.append(Paragraph(
        "<b>Diagnostic Analysis:</b> Standard web frameworks (like Node.js/Flask) hide OS concurrency and DB indexing under high-level abstractions. To impress evaluators and make this project worthy of capstones, publications, or hackathons, the team must make <b>OS Kernel principles</b> (Scheduling, IPC, Synchronization, Telemetry) and <b>DBMS Engine internals</b> (Spatial GIS Indexing, Pessimistic Locking, Active Triggers, Stored Procedures) <b>explicit, demonstrable core features</b>.",
        body_style
    ))
    story.append(Spacer(1, 8))

    # Section 2: Deep OS Concepts Integration Plan
    story.append(Paragraph("2. Deep Operating System (OS) Integration Strategy", h1_style))
    
    story.append(Paragraph("A. Custom Priority Scheduler with Aging (OS CPU Scheduling &rarr; Evacuee Triage)", h2_style))
    story.append(Paragraph("&bull; <b>OS Concept:</b> Multi-Level Priority Queue (MLPQ) Preemptive Scheduling with Aging mechanism.", bullet_style))
    story.append(Paragraph("&bull; <b>Disaster Context:</b> Treat evacuee requests as <i>OS Processes</i> and shelter beds as <i>CPU Time Slots</i>. Urgent medical cases (Priority 0) preempt general requests (Priority 2).", bullet_style))
    story.append(Paragraph("&bull; <b>Aging Mechanism:</b> Implement an OS timer daemon. If a Priority 2 request waits past threshold <i>T</i>, its priority is dynamically bumped to prevent infinite starvation under severe disaster surges.", bullet_style))
    story.append(Paragraph("&bull; <b>Evaluator Demo:</b> Show a live OS Process State diagram (READY, RUNNING, PREEMPTED, AGED).", bullet_style))

    story.append(Paragraph("B. Thread Synchronization & Deadlock Avoidance (OS Concurrency)", h2_style))
    story.append(Paragraph("&bull; <b>Producer-Consumer Buffer:</b> Field updates and IoT flood sensor streams produce events into a thread-safe Bounded Buffer with POSIX/Python Mutexes & Semaphores.", bullet_style))
    story.append(Paragraph("&bull; <b>Banker's Algorithm for Multi-Resource Bundles:</b> When an evacuee needs a bundle (1 Bed + 1 Oxygen Cylinder + 1 Transport Unit), run Dijkstra's Banker's Algorithm to verify system state safety before allocation, preventing deadlocks between shelters.", bullet_style))

    story.append(Paragraph("C. Inter-Process Communication (IPC) & Shared Memory", h2_style))
    story.append(Paragraph("&bull; <b>OS Concept:</b> UNIX Domain Sockets & Shared Memory (shmget/mmap) with Semaphores.", bullet_style))
    story.append(Paragraph("&bull; <b>Implementation:</b> Decouple high-throughput SOS intake from DB disk sync via Shared Memory queues for sub-millisecond intake during emergency spikes.", bullet_style))

    story.append(Paragraph("D. Real-Time OS Telemetry & System Load Simulator", h2_style))
    story.append(Paragraph("&bull; <b>Metrics Panel:</b> Display live CPU utilization, context switch counts, thread lock contention rates, and memory paging stats during a 1,000 requests/sec load test.", bullet_style))

    story.append(Spacer(1, 10))

    # Section 3: Advanced DBMS Concepts Integration Plan
    story.append(Paragraph("3. Advanced Database Management System (DBMS) Integration Strategy", h1_style))
    
    story.append(Paragraph("A. Spatial Indexing & Geospatial Queries (GIS / R-Trees)", h2_style))
    story.append(Paragraph("&bull; <b>DBMS Concept:</b> Spatial R-Tree Indexing and K-Nearest Neighbor (KNN) spatial operators.", bullet_style))
    story.append(Paragraph("&bull; <b>Implementation:</b> Store shelters and evacuees as <code>POINT(lat, long)</code> coordinates. Query nearest available shelters using spatial indices (e.g. <code>ST_Distance_Sphere</code> or PostGIS <code>&lt;-&gt;</code> operator) instead of application-level O(N) loops.", bullet_style))

    story.append(Paragraph("B. Pessimistic Concurrency Control & Isolation Levels", h2_style))
    story.append(Paragraph("&bull; <b>DBMS Concept:</b> Two-Phase Locking (2PL), Explicit Row Locks (<code>SELECT FOR UPDATE</code>), and ACID Transaction Isolation Levels.", bullet_style))
    story.append(Paragraph("&bull; <b>Race Condition Proof:</b> Run 100 simultaneous threads attempting to book the final 2 beds. Show that standard queries cause overbooking (negative capacity), whereas pessimistic <code>FOR UPDATE</code> locking guarantees exact zero-overbooking integrity.", bullet_style))

    story.append(Paragraph("C. Active Database Triggers & Stored Procedures", h2_style))
    story.append(Paragraph("&bull; <b>Capacity Trigger (90% Warning):</b> DB trigger fires <code>AFTER UPDATE</code> on shelter occupancy. When capacity &ge; 90%, it automatically writes an event to <code>alert_queue</code>.", bullet_style))
    story.append(Paragraph("&bull; <b>Atomic Stored Procedure (<code>sp_AllocateShelterWithFallback</code>):</b> Encapsulates multi-table operations (checking capacity, locking row, updating stock, inserting log) inside a single DB engine execution unit.", bullet_style))

    story.append(Spacer(1, 12))
    story.append(PageBreak()) # Clean page break for datasets & features

    # Section 4: India-Based Datasets
    story.append(Paragraph("4. India-Based Datasets for Realistic Simulation", h1_style))
    story.append(Paragraph(
        "To ground your project in actual Indian disaster management conditions, incorporate the following authoritative real-world datasets:",
        body_style
    ))

    india_ds_data = [
        [Paragraph("Dataset Name & Source", tbl_hdr),
         Paragraph("Data Type & Description", tbl_hdr),
         Paragraph("OSDBMS Project Application", tbl_hdr)],
        
        [Paragraph("<b>Kerala Floods 2018</b><br/>(Kaggle / Kerala SDMA)", tbl_cell),
         Paragraph("District-wise flood levels, affected population, relief camp counts, casualties.", tbl_cell),
         Paragraph("Use as historical workload replay data to simulate district disaster spikes and benchmark OS scheduler under stress.", tbl_cell)],

        [Paragraph("<b>India Disaster Resource Network (IDRN)</b><br/>(NIDM / MHA)", tbl_cell),
         Paragraph("National inventory of emergency equipment, specialized shelters, hospital beds across Indian districts.", tbl_cell),
         Paragraph("Populate shelter and resource inventory schema with realistic Indian municipal logistics capacity.", tbl_cell)],

        [Paragraph("<b>OpenStreetMap / HDX India Emergency Infrastructure</b>", tbl_cell),
         Paragraph("Geospatial shapefiles of schools, community halls, stadiums used as emergency shelters in India.", tbl_cell),
         Paragraph("Benchmark Spatial R-Tree Indexing and 5km KNN proximity queries on real Indian latitude/longitude coordinates.", tbl_cell)],

        [Paragraph("<b>State Shelter Board Data</b><br/>(DUSIB / NULM / SDMAs)", tbl_cell),
         Paragraph("Geocoded shelter list with capacities, drinking water, medical amenities, and gender accommodations.", tbl_cell),
         Paragraph("Test multi-criteria DBMS filtering and Banker's Algorithm multi-resource allocation bundles.", tbl_cell)]
    ]
    ds_table = Table(india_ds_data, colWidths=[120, 184, 200])
    ds_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), PRIMARY),
        ('PADDING', (0,0), (-1,-1), 5),
        ('BOX', (0,0), (-1,-1), 1, BORDER_COLOR),
        ('INNERGRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, BG_LIGHT])
    ]))
    story.append(ds_table)
    story.append(Spacer(1, 14))

    # Section 5: Cutting-Edge Extra Features
    story.append(Paragraph("5. Innovative Extra Features to Stand Out", h1_style))
    story.append(Paragraph(
        "Adding these high-impact features will make your project stand out in evaluations, hackathons, and research paper presentations:",
        body_style
    ))

    story.append(Paragraph("1. Offline-First SMS/LoRa Gateway (Low-Level OS IPC Serial Daemon)", h2_style))
    story.append(Paragraph("In major Indian floods (e.g. Chennai, Assam), cellular internet fails first! Build a low-level serial socket daemon in the OS backend that receives short SMS / USSD strings or LoRa mesh packets from field workers and parses them directly into the DBMS.", bullet_style))

    story.append(Paragraph("2. Multi-Lingual Voice Triage Intake (Vernacular Voice-to-SQL)", h2_style))
    story.append(Paragraph("Integrate speech-to-text (e.g. AI4Bharat Bhashini API) so non-literate evacuees or field workers can speak in Hindi, Assamese, or Malayalam. The backend translates spoken audio into structured OS triage priority flags.", bullet_style))

    story.append(Paragraph("3. AI/ML Flood Inundation & Capacity Predictor (Python Scikit-Learn + DBMS)", h2_style))
    story.append(Paragraph("Train a lightweight ML model (XGBoost/RandomForest) on IMD rainfall data to forecast shelter capacity exhaustion 6 hours in advance, triggering pro-active DB reallocation stored procedures.", bullet_style))

    story.append(Paragraph("4. Tamper-Proof Aid Audit Trail (Cryptographic Hash Chains in DBMS)", h2_style))
    story.append(Paragraph("To prevent aid diversion during relief operations, hash each supply allocation transaction (SHA-256 block chain) inside the database. Evaluators will appreciate this lightweight ledger implementation.", bullet_style))

    story.append(Paragraph("5. Live GIS Map & Heatmap Dashboard (OpenStreetMap / ISRO Bhuvan Integration)", h2_style))
    story.append(Paragraph("Display live spatial heatmaps of shelter occupancy rates and active evacuation buffer zones directly linked to spatial SQL queries.", bullet_style))

    story.append(Spacer(1, 14))

    # Section 6: Action Plan & Team Role Allocation
    story.append(Paragraph("6. Team Action Plan & Role Distribution", h1_style))

    team_plan_data = [
        [Paragraph("Team Member", tbl_hdr),
         Paragraph("Core Responsibility", tbl_hdr),
         Paragraph("Specific Deliverables & Technical Tasks", tbl_hdr)],

        [Paragraph("<b>Anushreya Tomar</b><br/>(Team Lead & DB)", tbl_cell),
         Paragraph("Database Engine & Concurrency Locks", tbl_cell),
         Paragraph("&bull; Implement Spatial R-Tree Indexing in MySQL/PostGIS.<br/>&bull; Write <code>SELECT FOR UPDATE</code> Pessimistic Transaction locks.<br/>&bull; Build DB 90% alert triggers and atomic stored procedures.", tbl_cell)],

        [Paragraph("<b>Akanchha Singh</b><br/>(Frontend & GIS)", tbl_cell),
         Paragraph("Interactive UI & GIS Heatmaps", tbl_cell),
         Paragraph("&bull; Build Leaflet.js / OpenStreetMap GIS dashboard.<br/>&bull; Add live OS Telemetry Panel (mutex wait times, context switches).<br/>&bull; Integrate India datasets (Kerala 2018 / IDRN).", tbl_cell)],

        [Paragraph("<b>Ishani Nautiyal</b><br/>(OS Scheduler)", tbl_cell),
         Paragraph("OS Scheduler & Triage Logic", tbl_cell),
         Paragraph("&bull; Code MLFQ Priority Queue with Aging daemon.<br/>&bull; Implement Dijkstra's Banker's Algorithm for resource bundles.<br/>&bull; Build process state transition visualizer.", tbl_cell)],

        [Paragraph("<b>Simarjeet Kaur</b><br/>(IPC & Testing)", tbl_cell),
         Paragraph("IPC Engine & Benchmark Suite", tbl_cell),
         Paragraph("&bull; Build Producer-Consumer Bounded Buffer with semaphores.<br/>&bull; Develop 1,000 concurrent request load tester.<br/>&bull; Prepare performance benchmark graphs for presentation.", tbl_cell)]
    ]
    team_table = Table(team_plan_data, colWidths=[110, 140, 254])
    team_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), SECONDARY),
        ('PADDING', (0,0), (-1,-1), 5),
        ('BOX', (0,0), (-1,-1), 1, BORDER_COLOR),
        ('INNERGRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, BG_LIGHT])
    ]))
    story.append(team_table)

    story.append(Spacer(1, 14))
    story.append(Paragraph("Conclusion & Roadmap", h2_style))
    story.append(Paragraph(
        "By implementing these OS kernel mechanisms, DBMS engine optimizations, and real Indian datasets, Team OSDBMS-V-2026-T135 will transform this project into an exemplary engineering milestone. This plan ensures maximum marks from evaluators and provides a solid foundation for hackathons and research publications.",
        body_style
    ))

    doc.build(story, canvasmaker=NumberedCanvas)

if __name__ == '__main__':
    target_path = r"c:\Users\anushreya\OneDrive\Desktop\pbl_phase2\OSDBMS_Project_Upgrade_Strategy_Plan.pdf"
    build_pdf(target_path)
    print(f"PDF successfully generated at: {target_path}")
