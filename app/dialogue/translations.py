from dataclasses import dataclass


@dataclass(frozen=True)
class LanguageConfig:
    locale: str
    label: str
    prompts: dict[str, str]
    yes_words: frozenset[str]
    no_words: frozenset[str]
    cancel_words: frozenset[str]
    human_words: frozenset[str]
    restart_words: frozenset[str]
    emergency_words: frozenset[str]


LANGUAGES: dict[str, LanguageConfig] = {
    "en-US": LanguageConfig(
        locale="en-US",
        label="English",
        prompts={
            "greeting": (
                "Hello. I can only help book a clinic appointment. What is the patient's name?"
            ),
            "ask_name": "What is the patient's name?",
            "ask_specialty": (
                "Which clinic or specialty do you need, for example general medicine, "
                "cardiology, dermatology, pediatrics, or dental?"
            ),
            "ask_date": (
                "What date would you like? You can say September 23, type 9/23, "
                "or use a full date such as 2026-09-23."
            ),
            "ask_time": (
                "What time would you like between 08:00 and 17:00? You can say 9 AM "
                "or 9:30 AM, or use 24-hour time such as 14:30."
            ),
            "confirm": (
                "Please confirm: {name}, {specialty}, on {date} at {time}. Say yes to "
                "book or no to change the time."
            ),
            "booked": (
                "Your demo appointment is booked. Confirmation code {code}. This demo "
                "does not connect to a real hospital."
            ),
            "slot_taken": (
                "That time is already booked in this demo. Please choose another time "
                "between 08:00 and 17:00."
            ),
            "invalid_date": (
                "I could not validate that date. Try September 23, 9/23, or a full "
                "date such as 2026-09-23, within the next 365 days."
            ),
            "invalid_time": (
                "I could not validate that time. Try 9 AM, 9:30 AM, or 14:30, and "
                "choose a future time between 08:00 and 17:00."
            ),
            "not_yes_no": "Please say yes to book, or no to choose another time.",
            "cancelled": "The booking conversation has been cancelled. No appointment was created.",
            "transfer": (
                "I will stop the automated booking flow and mark this demo for "
                "receptionist assistance."
            ),
            "restarted": "The booking has been restarted. What is the patient's name?",
            "task_only": "I can only help with appointment booking. What is the patient's name?",
            "emergency": (
                "This booking bot cannot handle emergencies or give medical advice. "
                "Please contact your local emergency service or a qualified clinician "
                "now."
            ),
        },
        yes_words=frozenset({"yes", "yeah", "yep", "confirm", "book", "correct"}),
        no_words=frozenset(
            {"no", "nope", "not", "don't", "can't", "cannot", "never", "change", "wrong"}
        ),
        cancel_words=frozenset({"cancel", "stop", "quit"}),
        human_words=frozenset({"human", "receptionist", "agent", "operator"}),
        restart_words=frozenset({"restart", "start over", "again"}),
        emergency_words=frozenset(
            {"emergency", "chest pain", "cannot breathe", "can't breathe", "unconscious"}
        ),
    ),
    "si-LK": LanguageConfig(
        locale="si-LK",
        label="සිංහල",
        prompts={
            "greeting": ("ආයුබෝවන්. මට උපකාර කළ හැක්කේ වෛද්‍ය හමුවක් වෙන්කර ගැනීමට පමණි. රෝගියාගේ නම කුමක්ද?"),
            "ask_name": "රෝගියාගේ නම කුමක්ද?",
            "ask_specialty": (
                "ඔබට අවශ්‍ය සායනය හෝ විශේෂඥ අංශය කුමක්ද? උදාහරණයක් ලෙස සාමාන්‍ය වෛද්‍ය, හෘද, සම, ළමා හෝ දන්ත."
            ),
            "ask_date": (
                "ඔබට අවශ්‍ය දිනය කුමක්ද? කරුණාකර 2026-09-10 වැනි වසර-මාසය-දිනය ආකාරයෙන් කියන්න හෝ ටයිප් කරන්න."
            ),
            "ask_time": (
                "08:00 සිට 17:00 අතර ඔබට අවශ්‍ය වේලාව කුමක්ද? 10:30 වැනි පැය-මිනිත්තු ආකාරයෙන් කියන්න හෝ ටයිප් කරන්න."
            ),
            "confirm": (
                "කරුණාකර තහවුරු කරන්න: {name}, {specialty}, {date} දින {time} ට. වෙන් "
                "කිරීමට ඔව් කියන්න, වේලාව වෙනස් කිරීමට නැහැ කියන්න."
            ),
            "booked": (
                "ඔබගේ ආදර්ශ හමුව වෙන් කර ඇත. තහවුරු කිරීමේ කේතය {code}. මෙය සැබෑ රෝහලකට සම්බන්ධ නොවන ආදර්ශයකි."
            ),
            "slot_taken": "එම වේලාව මේ ආදර්ශයේ දැනටමත් වෙන් කර ඇත. කරුණාකර වෙනත් වේලාවක් තෝරන්න.",
            "invalid_date": (
                "එම දිනය තහවුරු කළ නොහැකි විය. කරුණාකර 2026-09-10 වැනි වසර-මාසය-දිනය ආකාරය භාවිතා කරන්න."
            ),
            "invalid_time": (
                "එම වේලාව තහවුරු කළ නොහැකි විය. 08:00 සිට 17:00 අතර 10:30 වැනි පැය-මිනිත්තු ආකාරය භාවිතා කරන්න."
            ),
            "not_yes_no": "වෙන් කිරීමට ඔව් කියන්න, වෙනත් වේලාවක් තෝරන්න නම් නැහැ කියන්න.",
            "cancelled": "වෙන් කිරීමේ සංවාදය අවලංගු කර ඇත. කිසිදු හමුවක් නිර්මාණය කර නැත.",
            "transfer": ("ස්වයංක්‍රීය වෙන් කිරීම නවතා පිළිගැනීමේ නිලධාරී සහාය අවශ්‍ය බව සලකුණු කරමි."),
            "restarted": "වෙන් කිරීම නැවත ආරම්භ කර ඇත. රෝගියාගේ නම කුමක්ද?",
            "task_only": "මට උපකාර කළ හැක්කේ හමුවක් වෙන් කිරීමට පමණි. රෝගියාගේ නම කුමක්ද?",
            "emergency": (
                "මෙම වෙන් කිරීමේ බොට්ට හදිසි තත්ත්ව හෝ වෛද්‍ය උපදෙස් ලබා දිය නොහැක. "
                "කරුණාකර ඔබගේ ප්‍රදේශයේ හදිසි සේවාව හෝ සුදුසු වෛද්‍යවරයෙකු අමතන්න."
            ),
        },
        yes_words=frozenset({"ඔව්", "හරි", "තහවුරු"}),
        no_words=frozenset({"නැහැ", "නෑ", "එපා", "වෙනස්"}),
        cancel_words=frozenset({"අවලංගු", "නවත්වන්න"}),
        human_words=frozenset({"මනුෂ්‍ය", "නිලධාරී", "රෙසෙප්ෂන්"}),
        restart_words=frozenset({"නැවත", "ආයෙත්"}),
        emergency_words=frozenset({"හදිසි", "හුස්ම ගන්න බෑ", "පපුවේ වේදනාව"}),
    ),
    "ta-LK": LanguageConfig(
        locale="ta-LK",
        label="தமிழ்",
        prompts={
            "greeting": (
                "வணக்கம். நான் மருத்துவ நேரம் பதிவு செய்வதற்கு மட்டும் உதவ முடியும். நோயாளியின் பெயர் என்ன?"
            ),
            "ask_name": "நோயாளியின் பெயர் என்ன?",
            "ask_specialty": (
                "எந்த கிளினிக் அல்லது சிறப்பு பிரிவு வேண்டும்? உதாரணம்: பொது "
                "மருத்துவம், இதய மருத்துவம், தோல், குழந்தை மருத்துவம் அல்லது பல் "
                "மருத்துவம்."
            ),
            "ask_date": (
                "எந்த தேதியை விரும்புகிறீர்கள்? 2026-09-10 போன்ற ஆண்டு-மாதம்-நாள் "
                "வடிவில் சொல்லவும் அல்லது தட்டச்சு செய்யவும்."
            ),
            "ask_time": (
                "08:00 முதல் 17:00 வரை எந்த நேரம் வேண்டும்? 10:30 போன்ற மணி:நிமிடம் "
                "வடிவில் சொல்லவும் அல்லது தட்டச்சு செய்யவும்."
            ),
            "confirm": (
                "உறுதிப்படுத்தவும்: {name}, {specialty}, {date} அன்று {time}. பதிவு "
                "செய்ய ஆம், நேரத்தை மாற்ற இல்லை என்று சொல்லவும்."
            ),
            "booked": (
                "உங்கள் டெமோ நேரம் பதிவு செய்யப்பட்டது. உறுதிப்படுத்தல் குறியீடு "
                "{code}. இது உண்மையான மருத்துவமனைக்கு இணைக்கப்படவில்லை."
            ),
            "slot_taken": (
                "அந்த நேரம் இந்த டெமோவில் ஏற்கனவே பதிவு செய்யப்பட்டுள்ளது. வேறு நேரத்தைத் தேர்ந்தெடுக்கவும்."
            ),
            "invalid_date": (
                "அந்த தேதியை சரிபார்க்க முடியவில்லை. 2026-09-10 போன்ற ஆண்டு-மாதம்-நாள் வடிவைப் பயன்படுத்தவும்."
            ),
            "invalid_time": (
                "அந்த நேரத்தை சரிபார்க்க முடியவில்லை. 08:00 முதல் 17:00 வரை 10:30 "
                "போன்ற 24 மணி வடிவைப் பயன்படுத்தவும்."
            ),
            "not_yes_no": "பதிவு செய்ய ஆம் அல்லது வேறு நேரம் தேர்ந்தெடுக்க இல்லை என்று சொல்லவும்.",
            "cancelled": "பதிவு உரையாடல் ரத்து செய்யப்பட்டது. எந்த நேரமும் உருவாக்கப்படவில்லை.",
            "transfer": "தானியங்கி பதிவு நிறுத்தப்பட்டு வரவேற்பாளர் உதவி தேவை என குறிக்கப்படும்.",
            "restarted": "பதிவு மீண்டும் தொடங்கப்பட்டது. நோயாளியின் பெயர் என்ன?",
            "task_only": ("நான் மருத்துவ நேரம் பதிவு செய்வதற்கு மட்டும் உதவ முடியும். நோயாளியின் பெயர் என்ன?"),
            "emergency": (
                "இந்த பதிவு போட் அவசர நிலை அல்லது மருத்துவ ஆலோசனையை கையாளாது. உடனே "
                "உங்கள் உள்ளூர் அவசர சேவை அல்லது தகுதியான மருத்துவரை தொடர்பு கொள்ளவும்."
            ),
        },
        yes_words=frozenset({"ஆம்", "ஆமாம்", "சரி", "உறுதி"}),
        no_words=frozenset({"இல்லை", "வேண்டாம்", "மாற்று"}),
        cancel_words=frozenset({"ரத்து", "நிறுத்து"}),
        human_words=frozenset({"மனிதர்", "வரவேற்பாளர்", "அதிகாரி"}),
        restart_words=frozenset({"மீண்டும்", "மறுதொடக்கம்"}),
        emergency_words=frozenset({"அவசரம்", "மூச்சு விட முடியவில்லை", "மார்பு வலி"}),
    ),
    "hi-IN": LanguageConfig(
        locale="hi-IN",
        label="हिन्दी",
        prompts={
            "greeting": ("नमस्ते। मैं केवल क्लिनिक अपॉइंटमेंट बुक करने में मदद कर सकता हूँ। मरीज का नाम क्या है?"),
            "ask_name": "मरीज का नाम क्या है?",
            "ask_specialty": (
                "आपको कौन सा क्लिनिक या विशेषज्ञ चाहिए, जैसे सामान्य चिकित्सा, "
                "कार्डियोलॉजी, त्वचा, बाल रोग या दंत चिकित्सा?"
            ),
            "ask_date": (
                "आप किस तारीख को आना चाहते हैं? कृपया 2026-09-10 जैसे वर्ष-महीना-दिन प्रारूप में बोलें या लिखें।"
            ),
            "ask_time": (
                "08:00 से 17:00 के बीच कौन सा समय चाहिए? कृपया 10:30 जैसे घंटा:मिनट प्रारूप में बोलें या लिखें।"
            ),
            "confirm": (
                "कृपया पुष्टि करें: {name}, {specialty}, {date} को {time}. बुक करने के "
                "लिए हाँ और समय बदलने के लिए नहीं कहें।"
            ),
            "booked": (
                "आपका डेमो अपॉइंटमेंट बुक हो गया है। पुष्टि कोड {code}. यह डेमो किसी "
                "वास्तविक अस्पताल से जुड़ा नहीं है।"
            ),
            "slot_taken": "वह समय इस डेमो में पहले से बुक है। कृपया दूसरा समय चुनें।",
            "invalid_date": (
                "तारीख मान्य नहीं हुई। कृपया 2026-09-10 जैसा वर्ष-महीना-दिन प्रारूप इस्तेमाल करें।"
            ),
            "invalid_time": ("समय मान्य नहीं हुआ। कृपया 08:00 से 17:00 के बीच 10:30 जैसा 24-घंटे का समय दें।"),
            "not_yes_no": "बुक करने के लिए हाँ या दूसरा समय चुनने के लिए नहीं कहें।",
            "cancelled": "बुकिंग बातचीत रद्द कर दी गई है। कोई अपॉइंटमेंट नहीं बनाया गया।",
            "transfer": "मैं स्वचालित बुकिंग रोककर रिसेप्शनिस्ट सहायता का अनुरोध दर्ज कर रहा हूँ।",
            "restarted": "बुकिंग फिर से शुरू हुई। मरीज का नाम क्या है?",
            "task_only": "मैं केवल अपॉइंटमेंट बुकिंग में मदद कर सकता हूँ। मरीज का नाम क्या है?",
            "emergency": (
                "यह बुकिंग बॉट आपात स्थिति या चिकित्सा सलाह के लिए नहीं है। तुरंत अपनी "
                "स्थानीय आपात सेवा या योग्य चिकित्सक से संपर्क करें।"
            ),
        },
        yes_words=frozenset({"हाँ", "हां", "जी", "सही", "पुष्टि"}),
        no_words=frozenset({"नहीं", "बदलें", "बदलना"}),
        cancel_words=frozenset({"रद्द", "बंद"}),
        human_words=frozenset({"इंसान", "रिसेप्शनिस्ट", "एजेंट"}),
        restart_words=frozenset({"फिर", "दोबारा", "पुनः"}),
        emergency_words=frozenset({"आपात", "आपातकाल", "आपातकालीन", "सीने में दर्द", "सांस नहीं"}),
    ),
    "es-ES": LanguageConfig(
        locale="es-ES",
        label="Español",
        prompts={
            "greeting": (
                "Hola. Solo puedo ayudar a reservar una cita médica. ¿Cuál es el "
                "nombre del paciente?"
            ),
            "ask_name": "¿Cuál es el nombre del paciente?",
            "ask_specialty": (
                "¿Qué clínica o especialidad necesita, por ejemplo medicina general, "
                "cardiología, dermatología, pediatría o dental?"
            ),
            "ask_date": (
                "¿Qué fecha desea? Dígala o escríbala como año-mes-día, por ejemplo 2026-09-10."
            ),
            "ask_time": (
                "¿Qué hora desea entre 08:00 y 17:00? Dígala o escríbala como "
                "hora:minuto, por ejemplo 10:30."
            ),
            "confirm": (
                "Confirme: {name}, {specialty}, el {date} a las {time}. Diga sí para "
                "reservar o no para cambiar la hora."
            ),
            "booked": (
                "Su cita de demostración está reservada. Código de confirmación "
                "{code}. Esta demostración no está conectada a un hospital real."
            ),
            "slot_taken": "Esa hora ya está reservada en la demostración. Elija otra hora.",
            "invalid_date": (
                "No pude validar la fecha. Use el formato año-mes-día, por ejemplo 2026-09-10."
            ),
            "invalid_time": (
                "No pude validar la hora. Use formato de 24 horas entre 08:00 y 17:00, "
                "por ejemplo 10:30."
            ),
            "not_yes_no": "Diga sí para reservar o no para elegir otra hora.",
            "cancelled": "La conversación de reserva se canceló. No se creó ninguna cita.",
            "transfer": (
                "Detendré la reserva automática y marcaré la solicitud para ayuda de recepción."
            ),
            "restarted": "La reserva se reinició. ¿Cuál es el nombre del paciente?",
            "task_only": (
                "Solo puedo ayudar con reservas de citas. ¿Cuál es el nombre del paciente?"
            ),
            "emergency": (
                "Este bot de reservas no atiende emergencias ni da consejo médico. "
                "Contacte ahora con su servicio local de emergencias o un profesional "
                "sanitario cualificado."
            ),
        },
        yes_words=frozenset({"sí", "si", "confirmar", "correcto"}),
        no_words=frozenset({"no", "cambiar"}),
        cancel_words=frozenset({"cancelar", "parar"}),
        human_words=frozenset({"humano", "recepcionista", "agente"}),
        restart_words=frozenset({"reiniciar", "otra vez"}),
        emergency_words=frozenset({"emergencia", "dolor de pecho", "no puedo respirar"}),
    ),
    "fr-FR": LanguageConfig(
        locale="fr-FR",
        label="Français",
        prompts={
            "greeting": (
                "Bonjour. Je peux uniquement vous aider à réserver un rendez-vous "
                "médical. Quel est le nom du patient ?"
            ),
            "ask_name": "Quel est le nom du patient ?",
            "ask_specialty": (
                "De quelle clinique ou spécialité avez-vous besoin, par exemple "
                "médecine générale, cardiologie, dermatologie, pédiatrie ou dentaire ?"
            ),
            "ask_date": (
                "Quelle date souhaitez-vous ? Dites-la ou saisissez-la au format "
                "année-mois-jour, par exemple 2026-09-10."
            ),
            "ask_time": (
                "Quelle heure souhaitez-vous entre 08:00 et 17:00 ? Dites-la ou "
                "saisissez-la comme 10:30."
            ),
            "confirm": (
                "Veuillez confirmer : {name}, {specialty}, le {date} à {time}. Dites "
                "oui pour réserver ou non pour changer l'heure."
            ),
            "booked": (
                "Votre rendez-vous de démonstration est réservé. Code de confirmation "
                "{code}. Cette démo n'est reliée à aucun hôpital réel."
            ),
            "slot_taken": "Cette heure est déjà réservée dans la démo. Choisissez une autre heure.",
            "invalid_date": (
                "Je n'ai pas pu valider cette date. Utilisez le format "
                "année-mois-jour, par exemple 2026-09-10."
            ),
            "invalid_time": (
                "Je n'ai pas pu valider cette heure. Utilisez le format 24 heures "
                "entre 08:00 et 17:00, par exemple 10:30."
            ),
            "not_yes_no": "Dites oui pour réserver ou non pour choisir une autre heure.",
            "cancelled": (
                "La conversation de réservation a été annulée. Aucun rendez-vous n'a été créé."
            ),
            "transfer": (
                "J'arrête la réservation automatique et je signale une demande d'aide "
                "du secrétariat."
            ),
            "restarted": "La réservation a redémarré. Quel est le nom du patient ?",
            "task_only": (
                "Je peux uniquement aider à réserver un rendez-vous. Quel est le nom du patient ?"
            ),
            "emergency": (
                "Ce bot de réservation ne gère pas les urgences et ne donne pas de "
                "conseil médical. Contactez immédiatement les services d'urgence "
                "locaux ou un professionnel de santé qualifié."
            ),
        },
        yes_words=frozenset({"oui", "confirmer", "correct"}),
        no_words=frozenset({"non", "pas", "changer"}),
        cancel_words=frozenset({"annuler", "arrêter"}),
        human_words=frozenset({"humain", "secrétaire", "agent"}),
        restart_words=frozenset({"recommencer", "encore"}),
        emergency_words=frozenset({"urgence", "douleur poitrine", "je ne peux pas respirer"}),
    ),
    "de-DE": LanguageConfig(
        locale="de-DE",
        label="Deutsch",
        prompts={
            "greeting": (
                "Hallo. Ich kann nur bei der Buchung eines Arzttermins helfen. Wie "
                "heißt der Patient?"
            ),
            "ask_name": "Wie heißt der Patient?",
            "ask_specialty": (
                "Welche Klinik oder Fachrichtung benötigen Sie, zum Beispiel "
                "Allgemeinmedizin, Kardiologie, Dermatologie, Pädiatrie oder "
                "Zahnmedizin?"
            ),
            "ask_date": (
                "Welches Datum möchten Sie? Bitte als Jahr-Monat-Tag sagen oder "
                "eingeben, zum Beispiel 2026-09-10."
            ),
            "ask_time": (
                "Welche Uhrzeit möchten Sie zwischen 08:00 und 17:00? Bitte als "
                "Stunde:Minute sagen oder eingeben, zum Beispiel 10:30."
            ),
            "confirm": (
                "Bitte bestätigen: {name}, {specialty}, am {date} um {time}. Sagen Sie "
                "ja zum Buchen oder nein, um die Uhrzeit zu ändern."
            ),
            "booked": (
                "Ihr Demo-Termin ist gebucht. Bestätigungscode {code}. Diese Demo ist "
                "nicht mit einem echten Krankenhaus verbunden."
            ),
            "slot_taken": (
                "Diese Uhrzeit ist in der Demo bereits belegt. Bitte wählen Sie eine "
                "andere Uhrzeit."
            ),
            "invalid_date": (
                "Das Datum konnte nicht validiert werden. Verwenden Sie "
                "Jahr-Monat-Tag, zum Beispiel 2026-09-10."
            ),
            "invalid_time": (
                "Die Uhrzeit konnte nicht validiert werden. Verwenden Sie das "
                "24-Stunden-Format zwischen 08:00 und 17:00, zum Beispiel 10:30."
            ),
            "not_yes_no": "Sagen Sie ja zum Buchen oder nein, um eine andere Uhrzeit zu wählen.",
            "cancelled": "Die Buchung wurde abgebrochen. Es wurde kein Termin erstellt.",
            "transfer": (
                "Ich stoppe die automatische Buchung und markiere die Anfrage für "
                "Unterstützung durch die Rezeption."
            ),
            "restarted": "Die Buchung wurde neu gestartet. Wie heißt der Patient?",
            "task_only": "Ich kann nur bei der Terminbuchung helfen. Wie heißt der Patient?",
            "emergency": (
                "Dieser Buchungsbot ist nicht für Notfälle oder medizinische Beratung "
                "geeignet. Kontaktieren Sie sofort den örtlichen Notdienst oder "
                "medizinisches Fachpersonal."
            ),
        },
        yes_words=frozenset({"ja", "bestätigen", "richtig"}),
        no_words=frozenset({"nein", "nicht", "ändern"}),
        cancel_words=frozenset({"abbrechen", "stopp"}),
        human_words=frozenset({"mensch", "rezeption", "mitarbeiter"}),
        restart_words=frozenset({"neu starten", "nochmal"}),
        emergency_words=frozenset(
            {"notfall", "brustschmerz", "brustschmerzen", "kann nicht atmen"}
        ),
    ),
    "ar-SA": LanguageConfig(
        locale="ar-SA",
        label="العربية",
        prompts={
            "greeting": "مرحبًا. يمكنني فقط مساعدتك في حجز موعد طبي. ما اسم المريض؟",
            "ask_name": "ما اسم المريض؟",
            "ask_specialty": (
                "ما العيادة أو التخصص المطلوب، مثل الطب العام أو القلب أو الجلدية أو "
                "الأطفال أو الأسنان؟"
            ),
            "ask_date": "ما التاريخ المطلوب؟ قل أو اكتب التاريخ بصيغة سنة-شهر-يوم، مثل 2026-09-10.",
            "ask_time": "ما الوقت المطلوب بين 08:00 و17:00؟ قل أو اكتب الوقت مثل 10:30.",
            "confirm": (
                "يرجى التأكيد: {name}، {specialty}، بتاريخ {date} الساعة {time}. قل "
                "نعم للحجز أو لا لتغيير الوقت."
            ),
            "booked": (
                "تم حجز موعد العرض التجريبي. رمز التأكيد {code}. هذا العرض غير متصل بمستشفى حقيقي."
            ),
            "slot_taken": "هذا الوقت محجوز بالفعل في العرض التجريبي. اختر وقتًا آخر.",
            "invalid_date": "تعذر التحقق من التاريخ. استخدم صيغة سنة-شهر-يوم مثل 2026-09-10.",
            "invalid_time": "تعذر التحقق من الوقت. استخدم نظام 24 ساعة بين 08:00 و17:00 مثل 10:30.",
            "not_yes_no": "قل نعم للحجز أو لا لاختيار وقت آخر.",
            "cancelled": "تم إلغاء محادثة الحجز ولم يتم إنشاء موعد.",
            "transfer": "سأوقف الحجز الآلي وأضع علامة لطلب مساعدة موظف الاستقبال.",
            "restarted": "تمت إعادة بدء الحجز. ما اسم المريض؟",
            "task_only": "يمكنني فقط المساعدة في حجز المواعيد. ما اسم المريض؟",
            "emergency": (
                "روبوت الحجز هذا لا يتعامل مع الحالات الطارئة ولا يقدم نصيحة طبية. "
                "اتصل فورًا بخدمة الطوارئ المحلية أو بممارس صحي مؤهل."
            ),
        },
        yes_words=frozenset({"نعم", "أجل", "تأكيد", "صحيح"}),
        no_words=frozenset({"لا", "تغيير"}),
        cancel_words=frozenset({"إلغاء", "توقف"}),
        human_words=frozenset({"موظف", "استقبال", "إنسان"}),
        restart_words=frozenset({"إعادة", "ابدأ من جديد"}),
        emergency_words=frozenset({"طوارئ", "ألم الصدر", "لا أستطيع التنفس"}),
    ),
    "zh-CN": LanguageConfig(
        locale="zh-CN",
        label="中文",
        prompts={
            "greeting": "您好。我只能帮助预约门诊。请问患者姓名是什么？",
            "ask_name": "请问患者姓名是什么？",
            "ask_specialty": "您需要哪个科室，例如全科、心脏科、皮肤科、儿科或牙科？",
            "ask_date": "您想预约哪一天？请按年-月-日说出或输入，例如 2026-09-10。",
            "ask_time": (
                "您想预约 08:00 到 17:00 之间的什么时间？请按小时:分钟说出或输入，例如 10:30。"
            ),
            "confirm": (
                "请确认：{name}，{specialty}，{date} {time}。说“是”进行预约，说“否”更改时间。"
            ),
            "booked": "您的演示预约已创建。确认码 {code}。此演示未连接真实医院。",
            "slot_taken": "该时间在演示中已被预约。请选择其他时间。",
            "invalid_date": "无法验证该日期。请使用年-月-日格式，例如 2026-09-10。",
            "invalid_time": (
                "无法验证该时间。请使用 08:00 到 17:00 之间的 24 小时格式，例如 10:30。"
            ),
            "not_yes_no": "请说“是”进行预约，或说“否”选择其他时间。",
            "cancelled": "预约对话已取消，没有创建预约。",
            "transfer": "我将停止自动预约，并标记需要前台人员协助。",
            "restarted": "预约流程已重新开始。请问患者姓名是什么？",
            "task_only": "我只能帮助预约。请问患者姓名是什么？",
            "emergency": (
                "此预约机器人不能处理紧急情况，也不能提供医疗建议。请立即联系当地急救服"
                "务或合格的医疗专业人员。"
            ),
        },
        yes_words=frozenset({"是", "好的", "确认", "对"}),
        no_words=frozenset({"否", "不", "没", "更改"}),
        cancel_words=frozenset({"取消", "停止"}),
        human_words=frozenset({"人工", "前台", "客服"}),
        restart_words=frozenset({"重新开始", "重来"}),
        emergency_words=frozenset({"紧急", "胸痛", "不能呼吸"}),
    ),
    "ja-JP": LanguageConfig(
        locale="ja-JP",
        label="日本語",
        prompts={
            "greeting": (
                "こんにちは。診療予約の受付だけをお手伝いします。患者さんのお名前を教えてください。"
            ),
            "ask_name": "患者さんのお名前を教えてください。",
            "ask_specialty": (
                "希望する診療科を教えてください。例：一般内科、循環器科、皮膚科、小児科、歯科。"
            ),
            "ask_date": "希望日はいつですか。2026-09-10 のように年-月-日で話すか入力してください。",
            "ask_time": (
                "08:00 から 17:00 の間で希望時間を教えてください。10:30 "
                "のように時:分で話すか入力してください。"
            ),
            "confirm": (
                "確認します。{name}、{specialty}、{date} の "
                "{time}。予約する場合は「はい」、時間を変更する場合は「いいえ」と言って"
                "ください。"
            ),
            "booked": (
                "デモ予約が完了しました。確認コードは {code} "
                "です。このデモは実際の病院には接続されていません。"
            ),
            "slot_taken": "その時間はデモですでに予約されています。別の時間を選んでください。",
            "invalid_date": (
                "日付を確認できませんでした。2026-09-10 のような年-月-日形式を使ってください。"
            ),
            "invalid_time": (
                "時間を確認できませんでした。08:00 から 17:00 の間で、10:30 "
                "のような24時間形式を使ってください。"
            ),
            "not_yes_no": (
                "予約する場合は「はい」、別の時間を選ぶ場合は「いいえ」と言ってください。"
            ),
            "cancelled": "予約会話をキャンセルしました。予約は作成されていません。",
            "transfer": "自動予約を停止し、受付スタッフの支援が必要として記録します。",
            "restarted": "予約を最初からやり直します。患者さんのお名前を教えてください。",
            "task_only": "私は診療予約だけをお手伝いします。患者さんのお名前を教えてください。",
            "emergency": (
                "この予約ボットは緊急対応や医療助言はできません。直ちに地域の救急サービ"
                "スまたは資格のある医療従事者へ連絡してください。"
            ),
        },
        yes_words=frozenset({"はい", "確認", "正しい"}),
        no_words=frozenset({"いいえ", "ない", "変更"}),
        cancel_words=frozenset({"キャンセル", "停止"}),
        human_words=frozenset({"人と話", "担当者", "受付", "スタッフ"}),
        restart_words=frozenset({"やり直し", "最初から"}),
        emergency_words=frozenset({"緊急", "胸が痛い", "息ができない"}),
    ),
}

SUPPORTED_LANGUAGE_LOCALES = frozenset(LANGUAGES.keys())
