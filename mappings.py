"""All data normalisation maps used by both app.py and fetch_data.py."""

from __future__ import annotations

_CANONICAL_SUBJECTS = [
    "English", "Mathematics", "Science", "Social Science", "EVS", "Regional Lang", "Other",
]

# Fuzzy-match an unknown subject string to the nearest canonical subject.
# Returns None if confidence is below threshold (caller should fall back to "Other").
def fuzzy_subject(raw: str, threshold: int = 72) -> str | None:
    try:
        from thefuzz import process as _fuzz
    except ImportError:
        return None
    if not raw or not raw.strip():
        return None
    result = _fuzz.extractOne(raw.strip(), _CANONICAL_SUBJECTS)
    if result and result[1] >= threshold:
        return result[0]
    # Also try against all SUBJECT_MAP keys so typos of known subjects score well
    kresult = _fuzz.extractOne(raw.strip().lower(), list(SUBJECT_MAP.keys()))
    if kresult and kresult[1] >= threshold:
        return SUBJECT_MAP.get(kresult[0])
    return None

STATE_TO_LANGUAGE = {
    "uttar_pradesh": "Hindi", "bihar": "Hindi", "rajasthan": "Hindi",
    "madhya_pradesh": "Hindi", "haryana": "Hindi", "himachal_pradesh": "Hindi",
    "delhi": "Hindi", "uttarakhand": "Hindi", "chhattisgarh": "Hindi", "jharkhand": "Hindi",
    "west_bengal": "Bengali",
    "karnataka": "Kannada",
    "kerala": "Malayalam",
    "maharashtra": "Marathi",
    "odisha": "Odia",
    "punjab": "Punjabi",
    "tamil_nadu": "Tamil",
    "andhra_pradesh": "Telugu",
    "telangana": "Telugu",
}

CLASS_LEVEL_FROM_GRADE = {
    1: "Primary (1-5)", 2: "Primary (1-5)", 3: "Primary (1-5)",
    4: "Primary (1-5)", 5: "Primary (1-5)",
    6: "High School (6-8)", 7: "High School (6-8)", 8: "High School (6-8)",
    9: "Secondary (9-10)", 10: "Secondary (9-10)",
    11: "Higher Secondary (11-12)", 12: "Higher Secondary (11-12)",
}

SUBJECT_MAP = {
    # English
    "english": "English", "eanglish": "English", "engl;ish": "English",
    "english grammer": "English", "english grammar": "English",
    "grammer english": "English", "grammar": "English",
    "english literature": "English", "eng": "English",
    # Mathematics
    "math": "Mathematics", "maths": "Mathematics", "mahth": "Mathematics",
    "mathematics": "Mathematics", "rekha garhi": "Mathematics",
    "math_algebra": "Mathematics", "math_geometry": "Mathematics",
    "ganit": "Mathematics", "vedic math": "Mathematics",
    # Science (merged: Biology, Chemistry, Physics, general Science)
    "science": "Science", "science project": "Science", "science_project": "Science",
    "biology": "Science", "biology ": "Science",
    "chemistry": "Science", "chemistry ": "Science",
    "physics": "Science", "phisics": "Science",
    "science_physics": "Science", "science_chemistry": "Science", "science_biology": "Science",
    "vigyan": "Science",
    # Social Science (merged: History, Geography, Civics, Economics, Political Science)
    "social science": "Social Science", "social science ": "Social Science",
    " social science ": "Social Science", "scocial science": "Social Science",
    "social_science": "Social Science", "social_science ": "Social Science",
    "history": "Social Science", "history ": "Social Science", "hiistory": "Social Science",
    "geography": "Social Science", "geography ": "Social Science", "geogrphy": "Social Science",
    "civics": "Social Science", "civics ": "Social Science",
    "economics": "Social Science", "political science": "Social Science",
    "social_studies_political_science": "Social Science",
    "social_studies_history": "Social Science",
    "social_studies_geography": "Social Science",
    "social_studies_economics": "Social Science",
    "itihas": "Social Science", "bhugol": "Social Science", "samajik vigyan": "Social Science",
    # EVS
    "e.v.s": "EVS", "evs": "EVS", "environment": "EVS",
    "environmental": "EVS", "environmantal": "EVS",
    "paryavaran": "EVS", "paryawaran": "EVS", "hamara parivesh": "EVS",
    "environmental studies": "EVS", "environmental science": "EVS",
    # Regional Lang (Hindi, Sanskrit, and all Indic / regional languages)
    "hindi": "Regional Lang", "hindi grammar": "Regional Lang",
    "hindi vyakaran": "Regional Lang", "hindi kawy": "Regional Lang",
    "vavyakaran": "Regional Lang", "hindi literature": "Regional Lang",
    "hindi_grammar": "Regional Lang",
    "sanskrit": "Regional Lang", "sanskrit ": "Regional Lang",
    "sanskrit grammar": "Regional Lang", "sanskrit_grammar": "Regional Lang",
    "sanskrit vyakaran": "Regional Lang",
    # Other Indic / regional languages → Regional Lang
    "bengali": "Regional Lang", "marathi": "Regional Lang", "tamil": "Regional Lang",
    "telugu": "Regional Lang", "kannada": "Regional Lang", "malayalam": "Regional Lang",
    "odia": "Regional Lang", "oriya": "Regional Lang", "punjabi": "Regional Lang",
    "gujarati": "Regional Lang", "urdu": "Regional Lang", "assamese": "Regional Lang",
    "maithili": "Regional Lang", "bhojpuri": "Regional Lang", "konkani": "Regional Lang",
    "nepali": "Regional Lang", "sindhi": "Regional Lang", "kashmiri": "Regional Lang",
    "dogri": "Regional Lang", "manipuri": "Regional Lang", "bodo": "Regional Lang",
    "santali": "Regional Lang",
    "second_language": "Regional Lang",
    # Other (all non-core subjects collapse to Other)
    "computer": "Other", "it": "Other", "computer science": "Other",
    "general knowledge": "Other", "genral knowedge": "Other",
    "physical education": "Other",
    "business studies": "Other",
    "moral education": "Other", "mahan vyaktiva": "Other",
    "agriculture": "Other", "agricultur": "Other",
    "agriculture ": "Other", "krishi vigyan": "Other",
    "home science": "Other", "grihkaushal": "Other",
    "grikaushal": "Other", "gruh darshika": "Other",
    "other": "Other",
    "grade shelf": "Other", "not mentioned": "Other",
}

SAMPLE_TYPE_MAP = {
    "notebook c.w": "Notebook (Classwork)",
    "notebook c.w & h.w": "Notebook (CW & HW)",
    "notebook h.w": "Notebook (Homework)",
    "notebook": "Notebook", "notebook ": "Notebook",
    "worksheet": "Worksheet",
    "objective_assessment": "Objective Assessment",
    "subjective_assessment": "Subjective Assessment",
    "hybrid_obj_subj_assessment": "Hybrid Assessment",
    "cursive_writing_notebook": "Cursive Writing",
    "textbook": "Textbook",
    "graphbook": "Graphbook",
    "board_image": "Board Image",
    "map_labelling": "Map Labelling",
    "record_notebook": "Record Notebook",
    "form": "Form",
}

GENDER_MAP = {
    "male": "Male", "female": "Female", "other": "Other", "not mentioned": "Not Mentioned",
}

BOARD_MAP = {
    # CBSE
    "central_board_of_secondary_education_cbse": "CBSE",
    "cbse": "CBSE", "c b s e": "CBSE", "c.b.s.e": "CBSE",
    # ICSE / CISCE
    "icse": "ICSE", "cisce": "ICSE",
    "national_examinations_board": "NIOS",
    # UP Board
    "up_board_of_high_school_intermediate_education": "UP Board",
    "up_board_of_high_school_and_intermediate_education": "UP Board",
    "up board of high school and intermediate education": "UP Board",
    "up_board_of_sec_sanskrit_education": "UP Sanskrit Board",
    "u p": "UP Board", "u.p": "UP Board",
    # Bihar
    "bihar_school_examination_board": "BSEB",
    "bihar_board_of_open_schooling_and_examination": "BBOSE",
    "bihar_sanskrit_shiksha_board": "Bihar Sanskrit Board",
    "bihar_state_madrasa_education_board": "Bihar Madrasa Board",
    # West Bengal
    "west_bengal_board_of_secondary_education": "WBBSE",
    "west_bengal_council_of_higher_secondary_education": "WBCHSE",
    "west_bengal_board_of_madrasah_education": "WB Madrasah Board",
    # Karnataka
    "karnataka_secondary_education_examination_board": "KSEEB",
    # Kerala
    "kerala_board_of_public_examination": "Kerala SSLC Board",
    "kerala_board_of_higher_secondary_education": "Kerala HSE Board",
    "board_of_vocational_higher_secondary_education": "Kerala VHSE Board",
    # Maharashtra
    "maharashtra_state_board_of_secondary_and_higher_secondary_education": "MSBSHSE",
    # Gujarat
    "gujarat_secondary_and_higher_secondary_education_board": "GSEB",
    # Generic State Boards
    "board_of_secondary_education": "State Board",
    "board_of_intermediate_education": "State Board",
    "board_of_school_education": "State Board",
    "state_board": "State Board", "state board": "State Board",
    "state_board_of_school_examinations_sec_board_of_higher_secondary": "State Board",
    # Himachal Pradesh
    "h_p_board_of_school_education": "HPBOSE",
    # Chhattisgarh
    "chhattisgarh_board_of_secondary_education": "CGBSE",
    "chhattisgarh_madrasa_board": "CG Madrasa Board",
    "chhattisgarh_sanskrit_board": "CG Sanskrit Board",
    # Goa
    "goa_board_of_secondary_and_higher_secondary_education": "GBSHSE",
    # Punjab
    "punjab_school_education_board": "PSEB",
    # Telangana
    "telangana_state_board_of_intermediate_education": "TSBIE",
    # Uttarakhand
    "uttarakhand_madrasa_education_board": "UK Madrasa Board",
    # Jammu & Kashmir
    "the_j_k_state_board_of_school_education": "JKBOSE",
    # North-East
    "meghalaya_board_of_school_education": "MBOSE",
    "mizoram_board_of_school_education": "MBSE",
    "nagaland_board_of_school_education": "NBSE",
    "tripura_board_of_secondary_education": "TBSE",
    # Assam
    "assam_sanskrit_board": "Assam Sanskrit Board",
    "assam_higher_secondary_education_council": "AHSEC",
    # Jharkhand
    "jharkhand_academic_council": "JAC",
    # Rajasthan Open
    "rajasthan_state_open_school": "RSOS",
    # Telangana Open
    "telangana_open_school_society": "TOSS",
    # Andhra Pradesh Open
    "ap_open_school_society": "APOSS",
    # Chhattisgarh Open
    "chhattisgarh_state_open_school": "CG Open School",
    # West Bengal
    "the_west_bengal_council_of_rabindra_open_schooling": "WB Rabindra OS",
    "west_bengal_state_council_of_technical_vocational_education": "WBSCTE",
    # Karnataka PUC
    "govt_of_karnataka_dept_of_pre-university_education": "KA PUC Board",
    # CISCE (full slug)
    "council_for_the_indian_school_certificate_examinations_cisce": "CISCE",
    # State Higher Secondary Council (generic)
    "council_of_higher_secondary_education": "State HSE Board",
    # NIOS (full slug)
    "national_institute_of_open_schooling_nios": "NIOS",
    # Uttarakhand Sanskrit
    "uttrakhand_sanskrit_shiksha_parishad": "UK Sanskrit Board",
    # MP
    "m_p_state_open_school_education_board": "MP Open Board",
    # International / Private / Minority
    "cambridge_assessment_international_examinations": "Cambridge",
    "international_baccalaureate": "IB",
    "pearson_edexcel_ltd": "Edexcel",
    "mauritius_examination_syndicate": "MES",
    "northwest_accreditation_commission_nwac": "NWAC",
    "dayalbagh_educational_institute": "Dayalbagh",
    "jamia_milia_islamia": "Jamia Millia",
    "banasthali_vidyapith": "Banasthali",
    "bhutan_council_for_school_examinations_assessment": "BCSEA",
    "indian_council_for_hindi_sanskrit_education": "ICHSE",
    "maharishi_patanjali_sanskrit_sansthan": "MP Sanskrit Board",
    "sampurnanand_sanskrit_vishwavidyalay": "SSV",
    # Madrasa / Urdu / AMU
    "state_madrassa_education_board": "State Madrasa Board",
    "urdu_education_board": "Urdu Education Board",
    "aligarh_muslim_university_board": "AMU Board",
    # Fallback
    "not mentioned": "Not Mentioned",
}

BLOCK_MAP = {
    "arajilines": "Arajilines", "baragaon": "Baragaon", "chiraigaon": "Chiraigaon",
    "k.v.p": "KVP", "kvp": "KVP",
    "nagar nigam": "Nagar Nigam", "nagar_nigam": "Nagar Nigam",
    "sewapuri": "Sewapuri", "sewapuri ": "Sewapuri", "sewpuri": "Sewapuri",
    "not mentioned": "Not Mentioned",
}

SCHOOL_NORMALIZATIONS = {
    "u ps bohar": "UPS Bohar", "ups bohar": "UPS Bohar",
    "u ps ramana": "UPS Ramana", "ups ramana": "UPS Ramana",
    "u ps anei": "UPS Anei", "ups anei": "UPS Anei",
    "u ps lachhapur": "UPS Lachhapur",
    "cs rustampur": "CS Rustampur", "cs dholapur": "CS Dholapur",
    "ku ps kamauli": "KUPS Kamauli", "kups kamauli": "KUPS Kamauli",
    "cs pracheen": "CS Pracheen",
    "cs dehalivinayak": "CS Dehlivinayak", "cs dehalivinayak ": "CS Dehlivinayak",
    "cs dehlivinayak": "CS Dehlivinayak", "cs delhivinayak": "CS Dehlivinayak",
    "cs deyeepur ": "CS Deyeepur", "cs gairaha": "CS Gairaha",
    "cs kardhana": "CS Kardhana",
    "ku ps amani": "KUPS Amini", "ku ps amini": "KUPS Amini",
    "ku ps amini ": "KUPS Amini", "k u ps amani": "KUPS Amini",
    "u ps tikari": "UPS Tikari",
    "u ps vihara": "UPS Vihara", "u ps vihara ": "UPS Vihara", "u ps vihra": "UPS Vihara",
}

SUBJ_CAT_MAP = {
    # Canonical subjects pass through unchanged
    "English": "English",
    "Mathematics": "Mathematics",
    "Science": "Science",
    "Social Science": "Social Science",
    "EVS": "EVS",
    "Regional Lang": "Regional Lang",
    "Other": "Other", "Not Mentioned": "Other",
    # Legacy intermediate values (in case old cached parquet is loaded)
    "English Grammar": "English",
    "Hindi": "Regional Lang", "Hindi Grammar": "Regional Lang", "Hindi Literature": "Regional Lang",
    "Sanskrit": "Regional Lang", "Sanskrit Grammar": "Regional Lang",
    "Biology": "Science", "Chemistry": "Science", "Physics": "Science",
    "History": "Social Science", "Geography": "Social Science",
    "Civics": "Social Science", "Economics": "Social Science", "Political Science": "Social Science",
    "Hindi / Regional": "Regional Lang",
}
