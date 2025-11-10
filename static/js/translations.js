/**
 * Multi-language Translation System
 * Supports: English (EN), Français (FR), Español (ES)
 * Brand name "DASHMET" is never translated
 */

const translations = {
    en: {
        // Navigation
        nav_features: "Features",
        nav_about: "About",
        nav_reviews: "Reviews",
        nav_employee_login: "Employee Login",
        nav_leader_login: "Leader Login",
        nav_admin_login: "Admin Login",
        
        // Hero Section
        hero_title: "Transform Your Operations",
        hero_subtitle: "Professional analytics platform for modern businesses",
        hero_description: "Streamline workflows, track metrics, and make data-driven decisions with our comprehensive management system.",
        hero_get_started: "Get Started",
        hero_learn_more: "Learn More",
        
        // Features Section
        features_title: "Powerful Features",
        features_subtitle: "Everything you need to manage your operations efficiently",
        feature_realtime_title: "Real-Time Analytics",
        feature_realtime_desc: "Monitor your operations with live dashboards and instant insights.",
        feature_team_title: "Team Collaboration",
        feature_team_desc: "Coordinate seamlessly with built-in communication tools.",
        feature_reports_title: "Custom Reports",
        feature_reports_desc: "Generate detailed reports tailored to your needs.",
        feature_secure_title: "Enterprise Security",
        feature_secure_desc: "Bank-level encryption and data protection.",
        feature_mobile_title: "Mobile Responsive",
        feature_mobile_desc: "Access your dashboard from any device, anywhere.",
        feature_support_title: "24/7 Support",
        feature_support_desc: "Round-the-clock assistance from our expert team.",
        
        // About Section
        about_title: "About DASHMET",
        about_subtitle: "Your trusted partner in operational excellence",
        about_description: "DASHMET is a comprehensive management platform designed to streamline your business operations. From employee management to production tracking, we provide the tools you need to succeed.",
        about_mission_title: "Our Mission",
        about_mission_desc: "To empower businesses with intuitive tools that drive efficiency and growth.",
        about_vision_title: "Our Vision",
        about_vision_desc: "To be the leading platform for operational management worldwide.",
        
        // Reviews Section
        reviews_title: "What Our Users Say",
        reviews_subtitle: "Trusted by teams worldwide",
        reviews_no_reviews: "No reviews yet. Be the first to share your experience!",
        reviews_loading: "Loading reviews...",
        reviews_load_more: "Load More Reviews",
        reviews_view_all: "View All Reviews",
        
        // Footer
        footer_company: "Department",
        footer_product: "DASHMET",
        footer_legal: "Legal",
        footer_about: "About Us",
        footer_features: "Features",
        footer_security: "Security",
        footer_compliance: "Compliance",
        footer_privacy: "Privacy Policy",
        footer_terms: "Terms of Service",
        footer_cookies: "Cookie Policy",
        footer_rights: "All rights reserved. Created by Gerald Nyah.",
        footer_description: "Professional analytics platform. Transform your operations with data-driven insights.",
        
        // Login Pages
        login_title: "Welcome Back",
        login_subtitle: "Sign in to your account",
        login_email: "Email Address",
        login_password: "Password",
        login_remember: "Remember me",
        login_forgot: "Forgot password?",
        login_submit: "Sign In",
        login_no_account: "Don't have an account?",
        login_signup: "Sign up",
        
        // Employee Login
        employee_login_title: "Employee Portal",
        employee_login_subtitle: "Access your dashboard",
        employee_login_phone: "Phone Number",
        employee_login_verification: "Verification Code",
        employee_login_send_code: "Send Code",
        employee_login_verify: "Verify & Login",
        employee_login_resend: "Resend Code",
        
        // Dashboard
        dashboard_welcome: "Welcome back",
        dashboard_overview: "Overview",
        dashboard_metrics: "Metrics",
        dashboard_reports: "Reports",
        dashboard_settings: "Settings",
        dashboard_logout: "Logout",
        dashboard_profile: "Profile",
        
        // Vacation Management
        vacation_title: "Vacation Management",
        vacation_overview: "Overview",
        vacation_requests: "Requests",
        vacation_pending: "Pending",
        vacation_approved: "Approved",
        vacation_denied: "Denied",
        vacation_create: "Create Request",
        vacation_start_date: "Start Date",
        vacation_end_date: "End Date",
        vacation_return_date: "Return Date",
        vacation_duration: "Duration",
        vacation_days: "days",
        vacation_reason: "Reason",
        vacation_type: "Leave Type",
        vacation_status: "Status",
        vacation_submit: "Submit Request",
        vacation_cancel: "Cancel",
        vacation_approve: "Approve",
        vacation_deny: "Deny",
        vacation_conflicts: "Conflicts",
        vacation_upcoming: "Upcoming",
        vacation_recent: "Recent",
        vacation_employees: "Employees",
        vacation_activity: "Activity Log",
        vacation_constraints: "Constraints",
        vacation_my_requests: "My Requests",
        vacation_pending_approval: "Pending Approval",
        vacation_balance: "Vacation Balance",
        vacation_hours_available: "Hours Available",
        vacation_coverage_plan: "Coverage Plan",
        vacation_emergency_contact: "Emergency Contact",
        vacation_blackout_periods: "Blackout Periods",
        
        // User Management
        user_management: "User Management",
        user_add: "Add User",
        user_edit: "Edit User",
        user_delete: "Delete User",
        user_first_name: "First Name",
        user_last_name: "Last Name",
        user_email: "Email",
        user_phone: "Phone Number",
        user_role: "Role",
        user_department: "Department",
        user_status: "Status",
        user_active: "Active",
        user_inactive: "Inactive",
        user_save: "Save",
        user_cancel: "Cancel",
        
        // Production Dashboard
        production_title: "Production Dashboard",
        production_metrics: "Production Metrics",
        production_volume: "Volume",
        production_waste: "Waste",
        production_efficiency: "Efficiency",
        production_shift: "Shift",
        production_line: "Line",
        production_date: "Date",
        production_submit: "Submit Data",
        
        // Forms & Buttons
        form_required: "Required field",
        form_invalid_email: "Invalid email address",
        form_invalid_phone: "Invalid phone number",
        form_save: "Save",
        form_cancel: "Cancel",
        form_submit: "Submit",
        form_reset: "Reset",
        form_close: "Close",
        form_edit: "Edit",
        form_delete: "Delete",
        form_confirm: "Confirm",
        form_search: "Search",
        form_filter: "Filter",
        form_export: "Export",
        form_print: "Print",
        
        // Messages
        msg_success: "Success!",
        msg_error: "Error!",
        msg_warning: "Warning!",
        msg_info: "Information",
        msg_loading: "Loading...",
        msg_saving: "Saving...",
        msg_saved: "Saved successfully",
        msg_deleted: "Deleted successfully",
        msg_updated: "Updated successfully",
        msg_created: "Created successfully",
        msg_no_data: "No data available",
        msg_confirm_delete: "Are you sure you want to delete this item?",
        msg_confirm_logout: "Are you sure you want to logout?",
        msg_session_expired: "Your session has expired. Please login again.",
        
        // Errors
        error_required: "This field is required",
        error_invalid_format: "Invalid format",
        error_server: "Server error. Please try again later.",
        error_network: "Network error. Please check your connection.",
        error_unauthorized: "Unauthorized access",
        error_not_found: "Not found",
        error_validation: "Validation error",
        
        // Common
        common_yes: "Yes",
        common_no: "No",
        common_ok: "OK",
        common_back: "Back",
        common_next: "Next",
        common_previous: "Previous",
        common_page: "Page",
        common_of: "of",
        common_showing: "Showing",
        common_to: "to",
        common_entries: "entries",
        common_total: "Total",
        common_all: "All",
        common_none: "None",
        common_select: "Select",
        common_actions: "Actions",
        common_view: "View",
        common_download: "Download",
        common_upload: "Upload",
    },
    
    fr: {
        // Navigation
        nav_features: "Fonctionnalités",
        nav_about: "À propos",
        nav_reviews: "Avis",
        nav_employee_login: "Connexion Employé",
        nav_leader_login: "Connexion Leader",
        nav_admin_login: "Connexion Admin",
        
        // Hero Section
        hero_title: "Transformez Vos Opérations",
        hero_subtitle: "Plateforme d'analyse professionnelle pour les entreprises modernes",
        hero_description: "Rationalisez les flux de travail, suivez les métriques et prenez des décisions basées sur les données avec notre système de gestion complet.",
        hero_get_started: "Commencer",
        hero_learn_more: "En savoir plus",
        
        // Features Section
        features_title: "Fonctionnalités Puissantes",
        features_subtitle: "Tout ce dont vous avez besoin pour gérer vos opérations efficacement",
        feature_realtime_title: "Analyse en Temps Réel",
        feature_realtime_desc: "Surveillez vos opérations avec des tableaux de bord en direct et des informations instantanées.",
        feature_team_title: "Collaboration d'Équipe",
        feature_team_desc: "Coordonnez-vous facilement avec des outils de communication intégrés.",
        feature_reports_title: "Rapports Personnalisés",
        feature_reports_desc: "Générez des rapports détaillés adaptés à vos besoins.",
        feature_secure_title: "Sécurité d'Entreprise",
        feature_secure_desc: "Cryptage de niveau bancaire et protection des données.",
        feature_mobile_title: "Mobile Responsive",
        feature_mobile_desc: "Accédez à votre tableau de bord depuis n'importe quel appareil, n'importe où.",
        feature_support_title: "Support 24/7",
        feature_support_desc: "Assistance 24h/24 de notre équipe d'experts.",
        
        // About Section
        about_title: "À Propos de DASHMET",
        about_subtitle: "Votre partenaire de confiance pour l'excellence opérationnelle",
        about_description: "DASHMET est une plateforme de gestion complète conçue pour rationaliser vos opérations commerciales. De la gestion des employés au suivi de la production, nous fournissons les outils dont vous avez besoin pour réussir.",
        about_mission_title: "Notre Mission",
        about_mission_desc: "Donner aux entreprises des outils intuitifs qui favorisent l'efficacité et la croissance.",
        about_vision_title: "Notre Vision",
        about_vision_desc: "Être la plateforme leader pour la gestion opérationnelle dans le monde entier.",
        
        // Reviews Section
        reviews_title: "Ce Que Disent Nos Utilisateurs",
        reviews_subtitle: "Approuvé par des équipes du monde entier",
        reviews_no_reviews: "Pas encore d'avis. Soyez le premier à partager votre expérience!",
        reviews_loading: "Chargement des avis...",
        reviews_load_more: "Charger Plus d'Avis",
        reviews_view_all: "Voir Tous les Avis",
        
        // Footer
        footer_company: "Département",
        footer_product: "DASHMET",
        footer_legal: "Légal",
        footer_about: "À Propos",
        footer_features: "Fonctionnalités",
        footer_security: "Sécurité",
        footer_compliance: "Conformité",
        footer_privacy: "Politique de Confidentialité",
        footer_terms: "Conditions d'Utilisation",
        footer_cookies: "Politique des Cookies",
        footer_rights: "Tous droits réservés. Créé par Gerald Nyah.",
        footer_description: "Plateforme d'analyse professionnelle. Transformez vos opérations avec des informations basées sur les données.",
        
        // Login Pages
        login_title: "Bon Retour",
        login_subtitle: "Connectez-vous à votre compte",
        login_email: "Adresse E-mail",
        login_password: "Mot de Passe",
        login_remember: "Se souvenir de moi",
        login_forgot: "Mot de passe oublié?",
        login_submit: "Se Connecter",
        login_no_account: "Vous n'avez pas de compte?",
        login_signup: "S'inscrire",
        
        // Employee Login
        employee_login_title: "Portail Employé",
        employee_login_subtitle: "Accédez à votre tableau de bord",
        employee_login_phone: "Numéro de Téléphone",
        employee_login_verification: "Code de Vérification",
        employee_login_send_code: "Envoyer le Code",
        employee_login_verify: "Vérifier & Se Connecter",
        employee_login_resend: "Renvoyer le Code",
        
        // Dashboard
        dashboard_welcome: "Bon retour",
        dashboard_overview: "Aperçu",
        dashboard_metrics: "Métriques",
        dashboard_reports: "Rapports",
        dashboard_settings: "Paramètres",
        dashboard_logout: "Déconnexion",
        dashboard_profile: "Profil",
        
        // Vacation Management
        vacation_title: "Gestion des Vacances",
        vacation_overview: "Aperçu",
        vacation_requests: "Demandes",
        vacation_pending: "En Attente",
        vacation_approved: "Approuvé",
        vacation_denied: "Refusé",
        vacation_create: "Créer une Demande",
        vacation_start_date: "Date de Début",
        vacation_end_date: "Date de Fin",
        vacation_return_date: "Date de Retour",
        vacation_duration: "Durée",
        vacation_days: "jours",
        vacation_reason: "Raison",
        vacation_type: "Type de Congé",
        vacation_status: "Statut",
        vacation_submit: "Soumettre la Demande",
        vacation_cancel: "Annuler",
        vacation_approve: "Approuver",
        vacation_deny: "Refuser",
        vacation_conflicts: "Conflits",
        vacation_upcoming: "À Venir",
        vacation_recent: "Récent",
        vacation_employees: "Employés",
        vacation_activity: "Journal d'Activité",
        vacation_constraints: "Contraintes",
        vacation_my_requests: "Mes Demandes",
        vacation_pending_approval: "En Attente d'Approbation",
        vacation_balance: "Solde de Vacances",
        vacation_hours_available: "Heures Disponibles",
        vacation_coverage_plan: "Plan de Couverture",
        vacation_emergency_contact: "Contact d'Urgence",
        vacation_blackout_periods: "Périodes d'Interdiction",
        
        // User Management
        user_management: "Gestion des Utilisateurs",
        user_add: "Ajouter un Utilisateur",
        user_edit: "Modifier l'Utilisateur",
        user_delete: "Supprimer l'Utilisateur",
        user_first_name: "Prénom",
        user_last_name: "Nom",
        user_email: "E-mail",
        user_phone: "Numéro de Téléphone",
        user_role: "Rôle",
        user_department: "Département",
        user_status: "Statut",
        user_active: "Actif",
        user_inactive: "Inactif",
        user_save: "Enregistrer",
        user_cancel: "Annuler",
        
        // Production Dashboard
        production_title: "Tableau de Bord de Production",
        production_metrics: "Métriques de Production",
        production_volume: "Volume",
        production_waste: "Déchets",
        production_efficiency: "Efficacité",
        production_shift: "Équipe",
        production_line: "Ligne",
        production_date: "Date",
        production_submit: "Soumettre les Données",
        
        // Forms & Buttons
        form_required: "Champ obligatoire",
        form_invalid_email: "Adresse e-mail invalide",
        form_invalid_phone: "Numéro de téléphone invalide",
        form_save: "Enregistrer",
        form_cancel: "Annuler",
        form_submit: "Soumettre",
        form_reset: "Réinitialiser",
        form_close: "Fermer",
        form_edit: "Modifier",
        form_delete: "Supprimer",
        form_confirm: "Confirmer",
        form_search: "Rechercher",
        form_filter: "Filtrer",
        form_export: "Exporter",
        form_print: "Imprimer",
        
        // Messages
        msg_success: "Succès!",
        msg_error: "Erreur!",
        msg_warning: "Avertissement!",
        msg_info: "Information",
        msg_loading: "Chargement...",
        msg_saving: "Enregistrement...",
        msg_saved: "Enregistré avec succès",
        msg_deleted: "Supprimé avec succès",
        msg_updated: "Mis à jour avec succès",
        msg_created: "Créé avec succès",
        msg_no_data: "Aucune donnée disponible",
        msg_confirm_delete: "Êtes-vous sûr de vouloir supprimer cet élément?",
        msg_confirm_logout: "Êtes-vous sûr de vouloir vous déconnecter?",
        msg_session_expired: "Votre session a expiré. Veuillez vous reconnecter.",
        
        // Errors
        error_required: "Ce champ est obligatoire",
        error_invalid_format: "Format invalide",
        error_server: "Erreur du serveur. Veuillez réessayer plus tard.",
        error_network: "Erreur réseau. Veuillez vérifier votre connexion.",
        error_unauthorized: "Accès non autorisé",
        error_not_found: "Non trouvé",
        error_validation: "Erreur de validation",
        
        // Common
        common_yes: "Oui",
        common_no: "Non",
        common_ok: "OK",
        common_back: "Retour",
        common_next: "Suivant",
        common_previous: "Précédent",
        common_page: "Page",
        common_of: "de",
        common_showing: "Affichage",
        common_to: "à",
        common_entries: "entrées",
        common_total: "Total",
        common_all: "Tous",
        common_none: "Aucun",
        common_select: "Sélectionner",
        common_actions: "Actions",
        common_view: "Voir",
        common_download: "Télécharger",
        common_upload: "Téléverser",
    },
    
    es: {
        // Navigation
        nav_features: "Características",
        nav_about: "Acerca de",
        nav_reviews: "Reseñas",
        nav_employee_login: "Inicio de Sesión Empleado",
        nav_leader_login: "Inicio de Sesión Líder",
        nav_admin_login: "Inicio de Sesión Admin",
        
        // Hero Section
        hero_title: "Transforme Sus Operaciones",
        hero_subtitle: "Plataforma de análisis profesional para empresas modernas",
        hero_description: "Optimice flujos de trabajo, rastree métricas y tome decisiones basadas en datos con nuestro sistema de gestión integral.",
        hero_get_started: "Comenzar",
        hero_learn_more: "Más Información",
        
        // Features Section
        features_title: "Características Potentes",
        features_subtitle: "Todo lo que necesita para gestionar sus operaciones de manera eficiente",
        feature_realtime_title: "Análisis en Tiempo Real",
        feature_realtime_desc: "Monitoree sus operaciones con tableros en vivo y perspectivas instantáneas.",
        feature_team_title: "Colaboración en Equipo",
        feature_team_desc: "Coordínese sin problemas con herramientas de comunicación integradas.",
        feature_reports_title: "Informes Personalizados",
        feature_reports_desc: "Genere informes detallados adaptados a sus necesidades.",
        feature_secure_title: "Seguridad Empresarial",
        feature_secure_desc: "Cifrado de nivel bancario y protección de datos.",
        feature_mobile_title: "Diseño Responsivo",
        feature_mobile_desc: "Acceda a su panel desde cualquier dispositivo, en cualquier lugar.",
        feature_support_title: "Soporte 24/7",
        feature_support_desc: "Asistencia las 24 horas de nuestro equipo experto.",
        
        // About Section
        about_title: "Acerca de DASHMET",
        about_subtitle: "Su socio de confianza en excelencia operativa",
        about_description: "DASHMET es una plataforma de gestión integral diseñada para optimizar sus operaciones comerciales. Desde la gestión de empleados hasta el seguimiento de producción, proporcionamos las herramientas que necesita para tener éxito.",
        about_mission_title: "Nuestra Misión",
        about_mission_desc: "Empoderar a las empresas con herramientas intuitivas que impulsan la eficiencia y el crecimiento.",
        about_vision_title: "Nuestra Visión",
        about_vision_desc: "Ser la plataforma líder para la gestión operativa en todo el mundo.",
        
        // Reviews Section
        reviews_title: "Lo Que Dicen Nuestros Usuarios",
        reviews_subtitle: "Confiado por equipos en todo el mundo",
        reviews_no_reviews: "¡Aún no hay reseñas. Sea el primero en compartir su experiencia!",
        reviews_loading: "Cargando reseñas...",
        reviews_load_more: "Cargar Más Reseñas",
        reviews_view_all: "Ver Todas las Reseñas",
        
        // Footer
        footer_company: "Departamento",
        footer_product: "DASHMET",
        footer_legal: "Legal",
        footer_about: "Acerca de Nosotros",
        footer_features: "Características",
        footer_security: "Seguridad",
        footer_compliance: "Cumplimiento",
        footer_privacy: "Política de Privacidad",
        footer_terms: "Términos de Servicio",
        footer_cookies: "Política de Cookies",
        footer_rights: "Todos los derechos reservados. Creado por Gerald Nyah.",
        footer_description: "Plataforma de análisis profesional. Transforme sus operaciones con información basada en datos.",
        
        // Login Pages
        login_title: "Bienvenido de Nuevo",
        login_subtitle: "Inicie sesión en su cuenta",
        login_email: "Dirección de Correo Electrónico",
        login_password: "Contraseña",
        login_remember: "Recuérdame",
        login_forgot: "¿Olvidó su contraseña?",
        login_submit: "Iniciar Sesión",
        login_no_account: "¿No tiene una cuenta?",
        login_signup: "Registrarse",
        
        // Employee Login
        employee_login_title: "Portal de Empleados",
        employee_login_subtitle: "Acceda a su panel",
        employee_login_phone: "Número de Teléfono",
        employee_login_verification: "Código de Verificación",
        employee_login_send_code: "Enviar Código",
        employee_login_verify: "Verificar e Iniciar Sesión",
        employee_login_resend: "Reenviar Código",
        
        // Dashboard
        dashboard_welcome: "Bienvenido de nuevo",
        dashboard_overview: "Resumen",
        dashboard_metrics: "Métricas",
        dashboard_reports: "Informes",
        dashboard_settings: "Configuración",
        dashboard_logout: "Cerrar Sesión",
        dashboard_profile: "Perfil",
        
        // Vacation Management
        vacation_title: "Gestión de Vacaciones",
        vacation_overview: "Resumen",
        vacation_requests: "Solicitudes",
        vacation_pending: "Pendiente",
        vacation_approved: "Aprobado",
        vacation_denied: "Denegado",
        vacation_create: "Crear Solicitud",
        vacation_start_date: "Fecha de Inicio",
        vacation_end_date: "Fecha de Fin",
        vacation_return_date: "Fecha de Regreso",
        vacation_duration: "Duración",
        vacation_days: "días",
        vacation_reason: "Razón",
        vacation_type: "Tipo de Permiso",
        vacation_status: "Estado",
        vacation_submit: "Enviar Solicitud",
        vacation_cancel: "Cancelar",
        vacation_approve: "Aprobar",
        vacation_deny: "Denegar",
        vacation_conflicts: "Conflictos",
        vacation_upcoming: "Próximos",
        vacation_recent: "Reciente",
        vacation_employees: "Empleados",
        vacation_activity: "Registro de Actividad",
        vacation_constraints: "Restricciones",
        vacation_my_requests: "Mis Solicitudes",
        vacation_pending_approval: "Pendiente de Aprobación",
        vacation_balance: "Saldo de Vacaciones",
        vacation_hours_available: "Horas Disponibles",
        vacation_coverage_plan: "Plan de Cobertura",
        vacation_emergency_contact: "Contacto de Emergencia",
        vacation_blackout_periods: "Períodos de Bloqueo",
        
        // User Management
        user_management: "Gestión de Usuarios",
        user_add: "Agregar Usuario",
        user_edit: "Editar Usuario",
        user_delete: "Eliminar Usuario",
        user_first_name: "Nombre",
        user_last_name: "Apellido",
        user_email: "Correo Electrónico",
        user_phone: "Número de Teléfono",
        user_role: "Rol",
        user_department: "Departamento",
        user_status: "Estado",
        user_active: "Activo",
        user_inactive: "Inactivo",
        user_save: "Guardar",
        user_cancel: "Cancelar",
        
        // Production Dashboard
        production_title: "Panel de Producción",
        production_metrics: "Métricas de Producción",
        production_volume: "Volumen",
        production_waste: "Desperdicio",
        production_efficiency: "Eficiencia",
        production_shift: "Turno",
        production_line: "Línea",
        production_date: "Fecha",
        production_submit: "Enviar Datos",
        
        // Forms & Buttons
        form_required: "Campo obligatorio",
        form_invalid_email: "Dirección de correo electrónico no válida",
        form_invalid_phone: "Número de teléfono no válido",
        form_save: "Guardar",
        form_cancel: "Cancelar",
        form_submit: "Enviar",
        form_reset: "Restablecer",
        form_close: "Cerrar",
        form_edit: "Editar",
        form_delete: "Eliminar",
        form_confirm: "Confirmar",
        form_search: "Buscar",
        form_filter: "Filtrar",
        form_export: "Exportar",
        form_print: "Imprimir",
        
        // Messages
        msg_success: "¡Éxito!",
        msg_error: "¡Error!",
        msg_warning: "¡Advertencia!",
        msg_info: "Información",
        msg_loading: "Cargando...",
        msg_saving: "Guardando...",
        msg_saved: "Guardado exitosamente",
        msg_deleted: "Eliminado exitosamente",
        msg_updated: "Actualizado exitosamente",
        msg_created: "Creado exitosamente",
        msg_no_data: "No hay datos disponibles",
        msg_confirm_delete: "¿Está seguro de que desea eliminar este elemento?",
        msg_confirm_logout: "¿Está seguro de que desea cerrar sesión?",
        msg_session_expired: "Su sesión ha expirado. Por favor, inicie sesión nuevamente.",
        
        // Errors
        error_required: "Este campo es obligatorio",
        error_invalid_format: "Formato no válido",
        error_server: "Error del servidor. Por favor, intente más tarde.",
        error_network: "Error de red. Por favor, verifique su conexión.",
        error_unauthorized: "Acceso no autorizado",
        error_not_found: "No encontrado",
        error_validation: "Error de validación",
        
        // Common
        common_yes: "Sí",
        common_no: "No",
        common_ok: "OK",
        common_back: "Atrás",
        common_next: "Siguiente",
        common_previous: "Anterior",
        common_page: "Página",
        common_of: "de",
        common_showing: "Mostrando",
        common_to: "a",
        common_entries: "entradas",
        common_total: "Total",
        common_all: "Todos",
        common_none: "Ninguno",
        common_select: "Seleccionar",
        common_actions: "Acciones",
        common_view: "Ver",
        common_download: "Descargar",
        common_upload: "Subir",
    }
};

// Translation Manager
class TranslationManager {
    constructor() {
        this.currentLanguage = this.getStoredLanguage() || 'en';
        this.init();
    }
    
    init() {
        // Apply translations on page load
        this.applyTranslations();
        // Set up language switcher if present
        this.setupLanguageSwitcher();
    }
    
    getStoredLanguage() {
        try {
            return localStorage.getItem('dashmet_language') || 'en';
        } catch (e) {
            return 'en';
        }
    }
    
    setLanguage(lang) {
        if (!translations[lang]) {
            console.error(`Language ${lang} not supported`);
            return;
        }
        
        this.currentLanguage = lang;
        try {
            localStorage.setItem('dashmet_language', lang);
        } catch (e) {
            console.warn('Unable to store language preference');
        }
        
        this.applyTranslations();
        this.updateLanguageSwitcher();
        
        // Dispatch custom event for other scripts to listen to
        document.dispatchEvent(new CustomEvent('languageChanged', { 
            detail: { language: lang } 
        }));
    }
    
    translate(key) {
        return translations[this.currentLanguage][key] || translations.en[key] || key;
    }
    
    applyTranslations() {
        // Translate elements with data-translate attribute
        document.querySelectorAll('[data-translate]').forEach(element => {
            const key = element.getAttribute('data-translate');
            const translation = this.translate(key);
            
            if (element.tagName === 'INPUT' || element.tagName === 'TEXTAREA') {
                if (element.getAttribute('placeholder')) {
                    element.setAttribute('placeholder', translation);
                }
            } else {
                element.textContent = translation;
            }
        });
        
        // Translate placeholders
        document.querySelectorAll('[data-translate-placeholder]').forEach(element => {
            const key = element.getAttribute('data-translate-placeholder');
            const translation = this.translate(key);
            element.setAttribute('placeholder', translation);
        });
        
        // Translate aria-labels
        document.querySelectorAll('[data-translate-aria]').forEach(element => {
            const key = element.getAttribute('data-translate-aria');
            const translation = this.translate(key);
            element.setAttribute('aria-label', translation);
        });
        
        // Translate titles
        document.querySelectorAll('[data-translate-title]').forEach(element => {
            const key = element.getAttribute('data-translate-title');
            const translation = this.translate(key);
            element.setAttribute('title', translation);
        });
    }
    
    setupLanguageSwitcher() {
        const switcher = document.getElementById('language-switcher');
        if (!switcher) return;
        
        // Add click handlers to language options
        switcher.querySelectorAll('[data-lang]').forEach(option => {
            option.addEventListener('click', (e) => {
                e.preventDefault();
                const lang = option.getAttribute('data-lang');
                this.setLanguage(lang);
                // Close dropdown if exists
                const dropdown = document.getElementById('language-dropdown');
                if (dropdown) {
                    dropdown.classList.add('hidden');
                }
            });
        });
        
        this.updateLanguageSwitcher();
    }
    
    updateLanguageSwitcher() {
        const currentLangDisplay = document.getElementById('current-language');
        if (currentLangDisplay) {
            const langNames = {
                en: 'EN',
                fr: 'FR',
                es: 'ES'
            };
            currentLangDisplay.textContent = langNames[this.currentLanguage] || 'EN';
        }
        
        // Update active state
        document.querySelectorAll('[data-lang]').forEach(option => {
            const lang = option.getAttribute('data-lang');
            if (lang === this.currentLanguage) {
                option.classList.add('bg-blue-50', 'text-blue-700');
            } else {
                option.classList.remove('bg-blue-50', 'text-blue-700');
            }
        });
    }
}

// Initialize translation manager when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.translationManager = new TranslationManager();
    });
} else {
    window.translationManager = new TranslationManager();
}

// Expose translate function globally for dynamic content
window.translate = function(key) {
    return window.translationManager ? window.translationManager.translate(key) : key;
};
