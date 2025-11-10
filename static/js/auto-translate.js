/**
 * Professional Auto-Translation System for DASHMET
 * Automatically detects and translates text without manual tagging
 * Supports: English (EN), Español (ES)
 * Brand name "DASHMET" is preserved in all languages
 */

// Comprehensive translation dictionary
const TRANSLATIONS = {
    en: {
        // Navigation & Menu
        'Features': 'Features',
        'About': 'About',
        'Reviews': 'Reviews',
        'Employee Login': 'Employee Login',
        'Leader Login': 'Leader Login',
        'Admin Login': 'Admin Login',
        
        // Hero Section
        'Transform Your': 'Transform Your',
        'Operations': 'Operations',
        'A complete solution to monitor performance, verify inventory, and manage vacation requests, powered by enterprise-level tools.': 'A complete solution to monitor performance, verify inventory, and manage vacation requests, powered by enterprise-level tools.',
        'Login to Get Started Today': 'Login to Get Started Today',
        
        // Features Section
        'Powerful Features': 'Powerful Features',
        'Empower your team with the tools and insights you need to track, analyze, and elevate your operational performance.': 'Empower your team with the tools and insights you need to track, analyze, and elevate your operational performance.',
        'Real-time Analytics': 'Real-time Analytics',
        'Monitor OEE, production metrics, and waste with beautiful, interactive dashboards that provide actionable insights.': 'Monitor OEE, production metrics, and waste with beautiful, interactive dashboards that provide actionable insights.',
        'We also provide vacation management tools for supervisors and managers: employees can request time off, check availability, and receive real-time updates on their vacation request status.': 'We also provide vacation management tools for supervisors and managers: employees can request time off, check availability, and receive real-time updates on their vacation request status.',
        'Inventory Management': 'Inventory Management',
        'Track raw materials, and optimize inventory accuracy with automated workflows.': 'Track raw materials, and optimize inventory accuracy with automated workflows.',
        'Advanced Reporting': 'Advanced Reporting',
        'Generate comprehensive reports with exportable data and metrics visualization for informed decision-making.': 'Generate comprehensive reports with exportable data and metrics visualization for informed decision-making.',
        'Team Collaboration': 'Team Collaboration',
        'Coordinate across shifts with role-based access, real-time notifications, and integrated machine issues reporting tools.': 'Coordinate across shifts with role-based access, real-time notifications, and integrated machine issues reporting tools.',
        '24/7 Support': '24/7 Support',
        'Integrated ticketing system with dedicated technical support from our experts.': 'Integrated ticketing system with dedicated technical support from our experts.',
        'Security & Compliance': 'Security & Compliance',
        'Your data protected with enterprise-level security, end-to-end encryption, and strict compliance standards.': 'Your data protected with enterprise-level security, end-to-end encryption, and strict compliance standards.',
        
        // Common Actions
        'Get Started': 'Get Started',
        'Learn More': 'Learn More',
        'Contact Us': 'Contact Us',
        'Sign Up': 'Sign Up',
        'Submit': 'Submit',
        'Save': 'Save',
        'Cancel': 'Cancel',
        'Delete': 'Delete',
        'Edit': 'Edit',
        'Close': 'Close',
        'Confirm': 'Confirm',
        'Login': 'Login',
        'Logout': 'Logout',
        'Back': 'Back',
        'Next': 'Next',
        'Search': 'Search',
        'Filter': 'Filter',
        'Refresh': 'Refresh',
        'Update': 'Update',
        'Create': 'Create',
        'View': 'View',
        'Download': 'Download',
        'Upload': 'Upload',
        'Send': 'Send',
        'Apply': 'Apply',
        'Reset': 'Reset',
        
        // Status & Messages
        'Loading...': 'Loading...',
        'Success': 'Success',
        'Error': 'Error',
        'Warning': 'Warning',
        'Saved successfully': 'Saved successfully',
        'Failed to load': 'Failed to load',
        'Please try again': 'Please try again',
        'Are you sure?': 'Are you sure?',
        'This action cannot be undone': 'This action cannot be undone',
        
        // Form Labels
        'Name': 'Name',
        'Email': 'Email',
        'Password': 'Password',
        'Phone': 'Phone',
        'Address': 'Address',
        'Date': 'Date',
        'Time': 'Time',
        'Description': 'Description',
        'Comments': 'Comments',
        'Status': 'Status',
        'Type': 'Type',
        'Department': 'Department',
        'Role': 'Role',
        
        // Footer
        'All rights reserved': 'All rights reserved',
        'Privacy Policy': 'Privacy Policy',
        'Terms of Service': 'Terms of Service',
        'Cookie Policy': 'Cookie Policy',
        'Security': 'Security',
        'Compliance': 'Compliance',
        'Legal': 'Legal',
        'About Us': 'About Us',
        'Created by': 'Created by',
    },
    es: {
        // Navigation & Menu
        'Features': 'Características',
        'About': 'Acerca De',
        'Reviews': 'Reseñas',
        'Employee Login': 'Inicio Empleado',
        'Leader Login': 'Inicio Líder',
        'Admin Login': 'Inicio Admin',
        
        // Hero Section
        'Transform Your': 'Transforme Sus',
        'Operations': 'Operaciones',
        'A complete solution to monitor performance, verify inventory, and manage vacation requests, powered by enterprise-level tools.': 'Una solución completa para monitorear el rendimiento, verificar el inventario y gestionar solicitudes de vacaciones, impulsada por herramientas de nivel empresarial.',
        'Login to Get Started Today': 'Inicie Sesión para Comenzar Hoy',
        
        // Features Section
        'Powerful Features': 'Características Potentes',
        'Empower your team with the tools and insights you need to track, analyze, and elevate your operational performance.': 'Empodera a tu equipo con las herramientas y conocimientos que necesitas para rastrear, analizar y elevar tu rendimiento operativo.',
        'Real-time Analytics': 'Análisis en Tiempo Real',
        'Monitor OEE, production metrics, and waste with beautiful, interactive dashboards that provide actionable insights.': 'Monitorea OEE, métricas de producción y desperdicio con hermosos tableros interactivos que proporcionan información procesable.',
        'We also provide vacation management tools for supervisors and managers: employees can request time off, check availability, and receive real-time updates on their vacation request status.': 'También proporcionamos herramientas de gestión de vacaciones para supervisores y gerentes: los empleados pueden solicitar tiempo libre, verificar disponibilidad y recibir actualizaciones en tiempo real sobre el estado de su solicitud de vacaciones.',
        'Inventory Management': 'Gestión de Inventario',
        'Track raw materials, and optimize inventory accuracy with automated workflows.': 'Rastrea materias primas y optimiza la precisión del inventario con flujos de trabajo automatizados.',
        'Advanced Reporting': 'Informes Avanzados',
        'Generate comprehensive reports with exportable data and metrics visualization for informed decision-making.': 'Genera informes completos con datos exportables y visualización de métricas para tomar decisiones informadas.',
        'Team Collaboration': 'Colaboración en Equipo',
        'Coordinate across shifts with role-based access, real-time notifications, and integrated machine issues reporting tools.': 'Coordina entre turnos con acceso basado en roles, notificaciones en tiempo real y herramientas integradas de informes de problemas de máquinas.',
        '24/7 Support': 'Soporte 24/7',
        'Integrated ticketing system with dedicated technical support from our experts.': 'Sistema de tickets integrado con soporte técnico dedicado de nuestros expertos.',
        'Security & Compliance': 'Seguridad y Cumplimiento',
        'Your data protected with enterprise-level security, end-to-end encryption, and strict compliance standards.': 'Sus datos protegidos con seguridad de nivel empresarial, cifrado de extremo a extremo y estrictos estándares de cumplimiento.',
        
        // Common Actions
        'Get Started': 'Comenzar',
        'Learn More': 'Saber Más',
        'Contact Us': 'Contáctenos',
        'Sign Up': 'Registrarse',
        'Submit': 'Enviar',
        'Save': 'Guardar',
        'Cancel': 'Cancelar',
        'Delete': 'Eliminar',
        'Edit': 'Editar',
        'Close': 'Cerrar',
        'Confirm': 'Confirmar',
        'Login': 'Iniciar Sesión',
        'Logout': 'Cerrar Sesión',
        'Back': 'Atrás',
        'Next': 'Siguiente',
        'Search': 'Buscar',
        'Filter': 'Filtrar',
        'Refresh': 'Actualizar',
        'Update': 'Actualizar',
        'Create': 'Crear',
        'View': 'Ver',
        'Download': 'Descargar',
        'Upload': 'Subir',
        'Send': 'Enviar',
        'Apply': 'Aplicar',
        'Reset': 'Restablecer',
        
        // Status & Messages
        'Loading...': 'Cargando...',
        'Success': 'Éxito',
        'Error': 'Error',
        'Warning': 'Advertencia',
        'Saved successfully': 'Guardado exitosamente',
        'Failed to load': 'Error al cargar',
        'Please try again': 'Intente de nuevo',
        'Are you sure?': '¿Está seguro?',
        'This action cannot be undone': 'Esta acción no se puede deshacer',
        
        // Form Labels
        'Name': 'Nombre',
        'Email': 'Correo',
        'Password': 'Contraseña',
        'Phone': 'Teléfono',
        'Address': 'Dirección',
        'Date': 'Fecha',
        'Time': 'Hora',
        'Description': 'Descripción',
        'Comments': 'Comentarios',
        'Status': 'Estado',
        'Type': 'Tipo',
        'Department': 'Departamento',
        'Role': 'Rol',
        
        // Footer
        'All rights reserved': 'Todos los derechos reservados',
        'Privacy Policy': 'Política de Privacidad',
        'Terms of Service': 'Términos de Servicio',
        'Cookie Policy': 'Política de Cookies',
        'Security': 'Seguridad',
        'Compliance': 'Cumplimiento',
        'Legal': 'Legal',
        'About Us': 'Sobre Nosotros',
        'Created by': 'Creado por',
        'Created by Gerald Nyah': 'Creado por Gerald Nyah',
        
        // Additional common text
        'Join our current users who are already using our platform.': 'Únase a nuestros usuarios actuales que ya están usando nuestra plataforma.',
        'Login to Start today': 'Iniciar Sesión para Comenzar Hoy',
        'Professional analytics platform. Transform your operations with data-driven insights.': 'Plataforma de análisis profesional. Transforme sus operaciones con información basada en datos.',
        'All rights reserved. Created by Gerald Nyah.': 'Todos los derechos reservados. Creado por Gerald Nyah.',
        
        // About Section
        'About Bakery Metrics': 'Acerca de Bakery Metrics',
        'We\'re dedicated to transforming how your department operate through data-driven insights and modern technology. Our platform helps manager and supervisors make informed decisions, reduce waste, and optimize production and equipment efficiency.': 'Estamos dedicados a transformar cómo opera su departamento a través de información basada en datos y tecnología moderna. Nuestra plataforma ayuda a gerentes y supervisores a tomar decisiones informadas, reducir desperdicios y optimizar la eficiencia de producción y equipos.',
        'With years of experience in food production, we understand the unique challenges faced by modern companies and have built our solution to address them directly.': 'Con años de experiencia en producción de alimentos, entendemos los desafíos únicos que enfrentan las empresas modernas y hemos construido nuestra solución para abordarlos directamente.',
        'Login to Start Your journey here': 'Iniciar Sesión para Comenzar Su Viaje Aquí',
        'Positive': 'Positivo',
        'Active Users': 'Usuarios Activos',
        'Uptime': 'Tiempo Activo',
        'Support': 'Soporte',
        'Avg Efficiency Gain': 'Ganancia de Eficiencia Promedio',
        
        // Reviews Section
        'What Our Users Say': 'Lo Que Dicen Nuestros Usuarios',
        'See what other Supervisors and Managers are saying about their experience with our platform.': 'Vea lo que otros Supervisores y Gerentes dicen sobre su experiencia con nuestra plataforma.',
        'out of': 'de',
        'No ratings yet': 'Aún no hay calificaciones',
        'Based on': 'Basado en',
        'review': 'reseña',
        'reviews': 'reseñas',
        'Be the first to review!': '¡Sea el primero en reseñar!',
        
        // CTA Text
        'English': 'English',
        'Español': 'Español',
        'Language / Idioma': 'Idioma / Language',
        
        // Dashboard & Navigation
        'Dashboard': 'Tablero',
        'Production Management': 'Gestión de Producción',
        'Submit Report': 'Enviar Informe',
        'View Reports': 'Ver Informes',
        'Inventory': 'Inventario',
        'Issues': 'Problemas',
        'User Management': 'Gestión de Usuarios',
        'Profile': 'Perfil',
        'Settings': 'Configuración',
        'Navigation Menu': 'Menú de Navegación',
        'Open navigation menu': 'Abrir menú de navegación',
        'Close menu': 'Cerrar menú',
        
        // Issues Management
        'Issues Management': 'Gestión de Problemas',
        'Report machine issues and track resolution progress': 'Reportar problemas de máquinas y rastrear el progreso de resolución',
        'Report Issue': 'Reportar Problema',
        'Refresh': 'Actualizar',
        'All Issues': 'Todos los Problemas',
        'Open': 'Abierto',
        'In Progress': 'En Progreso',
        'Resolved': 'Resuelto',
        'Closed': 'Cerrado',
        'Issue ID': 'ID de Problema',
        'Machine': 'Máquina',
        'Priority': 'Prioridad',
        'Reported By': 'Reportado Por',
        'Low': 'Baja',
        'Medium': 'Media',
        'High': 'Alta',
        'Critical': 'Crítica',
        
        // Form Fields
        'Production Summary Submission': 'Envío de Resumen de Producción',
        'Complete production data entry with advanced features and real-time validation': 'Complete la entrada de datos de producción con funciones avanzadas y validación en tiempo real',
        'Basic Information': 'Información Básica',
        'Production Details': 'Detalles de Producción',
        'Review & Submit': 'Revisar y Enviar',
        'First Name': 'Nombre',
        'Last Name': 'Apellido',
        'Line Number': 'Número de Línea',
        'Shift': 'Turno',
        'Product': 'Producto',
        'Quantity': 'Cantidad',
        'Quality': 'Calidad',
        'Notes': 'Notas',
        
        // User Management
        'Total Users': 'Usuarios Totales',
        'Active': 'Activo',
        'Inactive': 'Inactivo',
        'Administrators': 'Administradores',
        'All accounts': 'Todas las cuentas',
        'Currently active': 'Actualmente activo',
        'Admin roles': 'Roles de administrador',
        'Add User': 'Agregar Usuario',
        'Edit User': 'Editar Usuario',
        'Delete User': 'Eliminar Usuario',
        
        // Profile
        'My Profile': 'Mi Perfil',
        'Account Settings': 'Configuración de Cuenta',
        'Change Password': 'Cambiar Contraseña',
        'Recent Activity': 'Actividad Reciente',
        'Recent Submissions': 'Envíos Recientes',
        
        // Confirmation Messages
        'Thank you': 'Gracias',
        'Your submission was successful.': 'Su envío fue exitoso.',
        'No data was submitted because an entry already exists for the selected day.': 'No se enviaron datos porque ya existe una entrada para el día seleccionado.',
        'Please contact your application administrator for assistance.': 'Por favor contacte a su administrador de aplicación para asistencia.',
        'Submitted at:': 'Enviado el:',
        'Checked at:': 'Verificado el:',
        'Return to Form': 'Volver al Formulario',
        
        // Vacation Management
        'Vacation Management': 'Gestión de Vacaciones',
        'Request Vacation': 'Solicitar Vacaciones',
        'My Requests': 'Mis Solicitudes',
        'Pending': 'Pendiente',
        'Approved': 'Aprobado',
        'Denied': 'Denegado',
        'Start Date': 'Fecha de Inicio',
        'End Date': 'Fecha de Finalización',
        'Reason': 'Razón',
        'Duration': 'Duración',
        'days': 'días',
        
        // Inventory
        'Inventory Overview': 'Resumen de Inventario',
        'Stock Levels': 'Niveles de Existencias',
        'Reorder': 'Reordenar',
        'In Stock': 'En Existencia',
        'Low Stock': 'Existencias Bajas',
        'Out of Stock': 'Agotado',
        
        // Reports
        'Report': 'Informe',
        'Reports': 'Informes',
        'Generate Report': 'Generar Informe',
        'Export': 'Exportar',
        'Print': 'Imprimir',
        'Date Range': 'Rango de Fechas',
        'From': 'Desde',
        'To': 'Hasta',
        
        // Time & Date
        'Today': 'Hoy',
        'Yesterday': 'Ayer',
        'This Week': 'Esta Semana',
        'This Month': 'Este Mes',
        'Last Month': 'Mes Pasado',
        'Custom Range': 'Rango Personalizado',
        
        // Actions & Buttons
        'Actions': 'Acciones',
        'More': 'Más',
        'Less': 'Menos',
        'Show More': 'Mostrar Más',
        'Show Less': 'Mostrar Menos',
        'Load More': 'Cargar Más',
        
        // Employee Login Page
        'Employee Access': 'Acceso de Empleado',
        'Sign in with your last name and US phone number.': 'Inicie sesión con su apellido y número de teléfono de EE. UU.',
        'Secured by Firebase Authentication': 'Asegurado por Autenticación Firebase',
        'Apellido': 'Apellido',
        'Enter your last name': 'Ingrese su apellido',
        'US Phone Number': 'Número de Teléfono de EE. UU.',
        'Enter US phone number (e.g., 5551234567)': 'Ingrese número de teléfono de EE. UU. (ej., 5551234567)',
        'US numbers only - Enter 10 digits without spaces or dashes': 'Solo números de EE. UU. - Ingrese 10 dígitos sin espacios ni guiones',
        'I agree to the': 'Acepto los',
        'Términos de Servicio': 'Términos de Servicio',
        'and': 'y',
        'Política de Privacidad': 'Política de Privacidad',
        'Send Verification Code': 'Enviar Código de Verificación',
        'Not an employee?': '¿No es empleado?',
        'Inicio Líder': 'Inicio Líder',
        
        // Welcome/Startup Pages
        'Welcome!': '¡Bienvenido!',
        'Choose where you\'d like to go': 'Elija a dónde le gustaría ir',
        'Bakery': 'Panadería',
        'Production': 'Producción',
        'Manage bakery operations and metrics': 'Gestione operaciones y métricas de panadería',
        'Track production data and efficiency': 'Rastree datos de producción y eficiencia',
        'View and manage vacation schedules': 'Ver y gestionar horarios de vacaciones',
        'Coming Soon': 'Próximamente',
        'Home': 'Inicio',
        'Cerrar Sesión': 'Cerrar Sesión',
        'Cerrar Sesion': 'Cerrar Sesión',
        
        // Dashboard Metrics
        'Average OEE': 'OEE Promedio',
        'Total Waste': 'Desperdicio Total',
        'Downtime Ratio': 'Ratio de Tiempo Inactivo',
        'Production Rate': 'Tasa de Producción',
        'vs last week': 'vs semana pasada',
        'lbs': 'lbs',
        'Export Report': 'Exportar Informe',
        'Submit Metrics': 'Enviar Métricas',
        'Refresh Data': 'Actualizar Datos',
        'Generate PDF analytics': 'Generar análisis PDF',
        'Add new data entry': 'Agregar nueva entrada de datos',
        'Update dashboard stats': 'Actualizar estadísticas del tablero',
        'Performance Overview': 'Resumen de Rendimiento',
        'Weekly OEE and Waste performance across both shifts': 'Rendimiento semanal de OEE y desperdicio en ambos turnos',
        'Current Week': 'Semana Actual',
        'Monday': 'Lunes',
        'Tuesday': 'Martes',
        'Wednesday': 'Miércoles',
        'Thursday': 'Jueves',
        'Friday': 'Viernes',
        'Saturday': 'Sábado',
        'Sunday': 'Domingo',
        'Target': 'Objetivo',
        'Performance Trend': 'Tendencia de Rendimiento',
        'OEE (%)': 'OEE (%)',
        'Waste (%)': 'Desperdicio (%)',
        
        // Leader/Manager Login
        'Welcome Back': 'Bienvenido de Nuevo',
        'Sign in to access your Bakery Daily Metrics dashboard.': 'Inicie sesión para acceder a su tablero de métricas diarias de panadería.',
        'Creado por Gerald Nyah': 'Creado por Gerald Nyah',
        'Email Address': 'Dirección de Correo Electrónico',
        'Enter your email address': 'Ingrese su dirección de correo electrónico',
        'Contraseña': 'Contraseña',
        'Enter your password': 'Ingrese su contraseña',
        'Sign In': 'Iniciar Sesión',
        'Need help?': '¿Necesita ayuda?',
        'Forgot your password?': '¿Olvidó su contraseña?',
        'Admin Access': 'Acceso de Administrador',
        'Secure Login Protected': 'Inicio de Sesión Seguro Protegido',
        'Términos de Servicio': 'Términos de Servicio',
        'Soporte': 'Soporte',
        
        // Vacation Hub - Supervisor View
        'Supervisor View': 'Vista de Supervisor',
        'Overview': 'Resumen',
        'Employees': 'Empleados',
        'Requests': 'Solicitudes',
        'Create Request': 'Crear Solicitud',
        'Constraints': 'Restricciones',
        'Activity Log': 'Registro de Actividad',
        'Total Employees': 'Total de Empleados',
        'Pending Requests': 'Solicitudes Pendientes',
        'Approved This Month': 'Aprobadas Este Mes',
        'Days Used (YTD)': 'Días Usados (Acumulado Anual)',
        'Upcoming': 'Próximos',
        'Pendiente': 'Pendiente',
        'Recent': 'Reciente',
        'Conflicts': 'Conflictos',
        'Upcoming Vacations (Next 30 Days)': 'Próximas Vacaciones (Próximos 30 Días)',
        'Rows per page:': 'Filas por página:',
        'Rows per page': 'Filas por página',
        'View Details': 'Ver Detalles',
        'Aprobado': 'Aprobado',
        'Review': 'Revisar',
        
        // Additional Common Terms
        'Search...': 'Buscar...',
        'Mon, Nov 10, 2025 — CST': 'Lun, 10 Nov, 2025 — CST',
        'Gerald Nyah': 'Gerald Nyah',
        'Back to Home': 'Volver al Inicio',
        'mm/dd/yyyy': 'mm/dd/aaaa',
        'to': 'a',
        
        // More Button and Label translations
        'Go to Dashboard': 'Ir al Tablero',
        'Go Back': 'Volver',
        'Continue': 'Continuar',
        'Previous': 'Anterior',
        'Next': 'Siguiente',
        'Finish': 'Finalizar',
        'Done': 'Hecho',
        'OK': 'OK',
        'Yes': 'Sí',
        'No': 'No',
        'Maybe': 'Tal vez',
        
        // Specific Label Issues
        'I agree to the Términos de Servicio and Política de Privacidad': 'Acepto los Términos de Servicio y Política de Privacidad',
        
        // Dashboard specific
        'Mon': 'Lun',
        'Tue': 'Mar',
        'Wed': 'Mié',
        'Thu': 'Jue',
        'Fri': 'Vie',
        'Sat': 'Sáb',
        'Sun': 'Dom',
        
        // Vacation specific additional
        'Bakery Lead': 'Líder de Panadería',
        'Bakery': 'Panadería',
        '2 days': '2 días',
        'Nov 24, 2025 - Nov 25, 2025': '24 Nov, 2025 - 25 Nov, 2025',
        
        // Additional time references
        'AM': 'AM',
        'PM': 'PM',
        'CST': 'CST',
        
        // More status indicators
        'Completed': 'Completado',
        'Processing': 'Procesando',
        'Failed': 'Fallido',
        'Waiting': 'Esperando',
        
        // Common error messages
        'An error occurred': 'Ocurrió un error',
        'Try again': 'Intentar de nuevo',
        'Something went wrong': 'Algo salió mal',
        'Connection error': 'Error de conexión',
        'Not found': 'No encontrado',
        'Access denied': 'Acceso denegado',
        'Invalid input': 'Entrada inválida',
        'Required field': 'Campo requerido',
        
        // More form placeholders
        'Select...': 'Seleccionar...',
        'Select an option': 'Seleccione una opción',
        'Choose': 'Elegir',
        'Pick a date': 'Seleccione una fecha',
        'Optional': 'Opcional',
        'Required': 'Requerido',
        
        // Sidebar Navigation (Dashboard)
        'Tablero': 'Tablero',
        'Bakery Metrics': 'Métricas de Panadería',
        'Submit Data': 'Enviar Datos',
        'Report Issues': 'Reportar Problemas',
        'Inventario': 'Inventario',
        'Inventory Tracking': 'Seguimiento de Inventario',
        'Help Center': 'Centro de Ayuda',
        
        // Dashboard Content
        'First Shift Performance': 'Rendimiento del Primer Turno',
        'Second Shift Performance': 'Rendimiento del Segundo Turno',
        'Current week operational metrics': 'Métricas operacionales de la semana actual',
        'OEE (1st Shift)': 'OEE (1er Turno)',
        'OEE (2nd Shift)': 'OEE (2do Turno)',
        'Waste (1st Shift)': 'Desperdicio (1er Turno)',
        'Waste (2nd Shift)': 'Desperdicio (2do Turno)',
        'Actividad Reciente': 'Actividad Reciente',
        'Performance Targets': 'Objetivos de Rendimiento',
        'Quick Actions': 'Acciones Rápidas',
        'Metrics submitted for Friday': 'Métricas enviadas para Viernes',
        'Metrics submitted for Thursday': 'Métricas enviadas para Jueves',
        'Metrics submitted for Wednesday': 'Métricas enviadas para Miércoles',
        'Metrics submitted for Tuesday': 'Métricas enviadas para Martes',
        'Metrics submitted for Monday': 'Métricas enviadas para Lunes',
        '8 hours ago': 'hace 8 horas',
        '4 days ago': 'hace 4 días',
        '5 days ago': 'hace 5 días',
        '2 hours ago': 'hace 2 horas',
        'hours ago': 'horas atrás',
        'days ago': 'días atrás',
        'Actual vs Target': 'Real vs Objetivo',
        'Target Met': 'Objetivo Cumplido',
        'Uptime Target': 'Objetivo de Tiempo Activo',
        'View Analytics': 'Ver Análisis',
        'Detailed performance metrics': 'Métricas de rendimiento detalladas',
        'Manage Inventory': 'Gestionar Inventario',
        'Track raw materials': 'Rastrear materias primas',
        'Equipment & quality issues': 'Problemas de equipo y calidad',
        
        // Submit Report / Submit Daily Metrics
        'Submit Daily Metrics': 'Enviar Métricas Diarias',
        'Enter your bakery\'s daily performance metrics for tracking and analysis': 'Ingrese las métricas de rendimiento diarias de su panadería para seguimiento y análisis',
        'Basic Info': 'Información Básica',
        'Metrics': 'Métricas',
        'Revisar': 'Revisar',
        'Start': 'Inicio',
        'Complete': 'Completar',
        'Record exists for Monday in 11-03-2025_11-07-2025. Please select a different day or week.': 'Ya existe un registro para el Lunes en 11-03-2025_11-07-2025. Por favor seleccione un día o semana diferente.',
        'Información Básica': 'Información Básica',
        'Select the week and day for your metrics submission': 'Seleccione la semana y el día para el envío de sus métricas',
        'Semana Actual': 'Semana Actual',
        'Day': 'Día',
        'Submitted By': 'Enviado Por',
        'Lunes': 'Lunes',
        'Siguiente': 'Siguiente',
        'Restablecer': 'Restablecer',
        'End of Day': 'Fin del Día',
        'Tips & Guidelines': 'Consejos y Guías',
        'Envíos Recientes': 'Envíos Recientes',
        'OEE Best Practice': 'Mejores Prácticas de OEE',
        'Target OEE should be ≥70%. Values above 85% are considered excellent.': 'El OEE objetivo debe ser ≥70%. Valores superiores al 85% se consideran excelentes.',
        'Waste Control': 'Control de Desperdicios',
        'Keep waste percentage below 3.75%. Higher values may indicate process issues.': 'Mantenga el porcentaje de desperdicio por debajo del 3.75%. Valores más altos pueden indicar problemas en el proceso.',
        'Submission Timing': 'Tiempo de Envío',
        'Submit metrics by end of day for accurate reporting and analysis.': 'Envíe las métricas al final del día para informes y análisis precisos.',
        'Friday Metrics': 'Métricas del Viernes',
        'Thursday Metrics': 'Métricas del Jueves',
        'Wednesday Metrics': 'Métricas del Miércoles',
        'Tuesday Metrics': 'Métricas del Martes',
        'Monday Metrics': 'Métricas del Lunes',
        'Completado': 'Completado',
        'View All Submissions': 'Ver Todos los Envíos',
        
        // Information Center / Help Center
        'Information Center': 'Centro de Información',
        'Help, Support, and System Information': 'Ayuda, Soporte e Información del Sistema',
        'Get Support': 'Obtener Soporte',
        'Submit Review': 'Enviar Reseña',
        'System Online': 'Sistema En Línea',
        'Secure Connection': 'Conexión Segura',
        'Announcements': 'Anuncios',
        'NEW': 'NUEVO',
        'System Update v2.1.5 Released': 'Actualización del Sistema v2.1.5 Publicada',
        'System': 'Sistema',
        'New features include enhanced reporting, improved mobile responsiveness, and better data visualization tools.': 'Las nuevas funciones incluyen informes mejorados, mayor capacidad de respuesta móvil y mejores herramientas de visualización de datos.',
        'December 15, 2024': '15 de Diciembre, 2024',
        'System Administrator': 'Administrador del Sistema',
        'Scheduled Maintenance Window': 'Ventana de Mantenimiento Programado',
        'Maintenance': 'Mantenimiento',
        'System will be offline for maintenance on December 20th from 2:00 AM to 4:00 AM EST. Please save your work beforehand.': 'El sistema estará fuera de línea para mantenimiento el 20 de diciembre de 2:00 AM a 4:00 AM EST. Por favor guarde su trabajo antes.',
        'Dec 20, 2:00 AM - 4:00 AM EST': '20 Dic, 2:00 AM - 4:00 AM EST',
        '2 hours duration': '2 horas de duración',
        'New AI Analytics Feature': 'Nueva Función de Análisis de IA',
        'Feature': 'Función',
        'Introducing AI-powered insights and recommendations to help optimize your bakery operations and improve efficiency.': 'Presentamos información y recomendaciones impulsadas por IA para ayudar a optimizar sus operaciones de panadería y mejorar la eficiencia.',
        'AI Powered': 'Impulsado por IA',
        'Boost Efficiency': 'Impulsar Eficiencia',
        
        // Support Center
        'Support Center': 'Centro de Soporte',
        'Response time: ~2 hours': 'Tiempo de respuesta: ~2 horas',
        'Support Available': 'Soporte Disponible',
        'Satisfaction Rate': 'Tasa de Satisfacción',
        'Avg Response': 'Respuesta Promedio',
        'Submit Support Ticket': 'Enviar Ticket de Soporte',
        'Priority Level': 'Nivel de Prioridad',
        'Category': 'Categoría',
        'Low - General Questions': 'Baja - Preguntas Generales',
        'Select a category': 'Seleccione una categoría',
        'Subject': 'Asunto',
        'Brief description of your issue': 'Breve descripción de su problema',
        'Descripción': 'Descripción',
        'Please provide detailed information about your issue or request': 'Por favor proporcione información detallada sobre su problema o solicitud',
        'All communications are encrypted and secure': 'Todas las comunicaciones están encriptadas y son seguras',
        'Submit Ticket': 'Enviar Ticket',
        'Your Recent Tickets': 'Sus Tickets Recientes',
        'No recent tickets found': 'No se encontraron tickets recientes',
        'Rate your experience:': 'Califique su experiencia:',
        'General Experience': 'Experiencia General',
        'Share your feedback about the system... (optional)': 'Comparta sus comentarios sobre el sistema... (opcional)',
        '0/999 characters': '0/999 caracteres',
        'Submit anonymously': 'Enviar anónimamente',
        'System Info': 'Información del Sistema',
        'Version': 'Versión',
        'Estado': 'Estado',
        'Online': 'En Línea',
        'Last Update': 'Última Actualización',
        'Dec 15, 2024': '15 Dic, 2024',
        'Tiempo Activo': 'Tiempo Activo',
        'Server Location': 'Ubicación del Servidor',
        'US East': 'Este de EE. UU.',
        'Quick Links': 'Enlaces Rápidos',
        'User Manual': 'Manual de Usuario',
        'Video Tutorials': 'Tutoriales en Video',
        'API Documentation': 'Documentación de API',
        'Community Forum': 'Foro de la Comunidad',
        'Frequently Asked Questions': 'Preguntas Frecuentes',
        'Search FAQ': 'Buscar FAQ',
        'No FAQs found matching your search.': 'No se encontraron FAQs que coincidan con su búsqueda.',
        'Need Additional Help?': '¿Necesita Ayuda Adicional?',
        'Our support team is here to assist you 24/7': 'Nuestro equipo de soporte está aquí para asistirlo 24/7',
        'Call Us': 'Llámenos',
        '24/7': '24/7',
        'Call us 24/7 for any app issues or support': 'Llámenos 24/7 para cualquier problema de la aplicación o soporte',
    }
};

class AutoTranslate {
    constructor() {
        this.currentLang = localStorage.getItem('app_language') || 'en';
        this.translations = TRANSLATIONS;
        this.originalTexts = new WeakMap(); // Store original texts
    }
    
    // Synchronous fallback translation
    t(text) {
        if (!text || typeof text !== 'string') return text;
        const trimmed = text.trim();
        
        // Never translate DASHMET
        if (trimmed === 'DASHMET' || trimmed.includes('DASHMET')) {
            return text;
        }
        
        // Skip numbers and special characters
        if (/^[\d\s\-\/:.]+$/.test(trimmed)) {
            return text;
        }
        
        // Try exact match first
        if (this.translations[this.currentLang]?.[trimmed]) {
            return this.translations[this.currentLang][trimmed];
        }
        
        // Fuzzy matching for similar phrases (case-insensitive)
        if (this.currentLang === 'es') {
            const lowerText = trimmed.toLowerCase();
            
            // Common patterns - add more as needed
            const patterns = {
                // Questions
                /need.*help/i: '¿Necesita Ayuda?',
                /forgot.*password/i: '¿Olvidó su contraseña?',
                
                // Time references
                /(\d+)\s*hours?\s*ago/i: (match, num) => `hace ${num} ${num === '1' ? 'hora' : 'horas'}`,
                /(\d+)\s*days?\s*ago/i: (match, num) => `hace ${num} ${num === '1' ? 'día' : 'días'}`,
                /(\d+)\s*minutes?\s*ago/i: (match, num) => `hace ${num} ${num === '1' ? 'minuto' : 'minutos'}`,
                
                // Metrics patterns
                /metrics?\s+submitted/i: 'Métricas enviadas',
                /submit.*metrics?/i: 'Enviar Métricas',
                /submit.*data/i: 'Enviar Datos',
                /submit.*report/i: 'Enviar Informe',
                
                // Common actions
                /view\s+all/i: 'Ver Todo',
                /view\s+details/i: 'Ver Detalles',
                /get\s+support/i: 'Obtener Soporte',
                /load\s+more/i: 'Cargar Más',
                /show\s+more/i: 'Mostrar Más',
                /show\s+less/i: 'Mostrar Menos',
                
                // Performance
                /first\s+shift/i: 'Primer Turno',
                /second\s+shift/i: 'Segundo Turno',
                /performance/i: 'Rendimiento',
                /metrics/i: 'Métricas',
                
                // Status
                /system\s+online/i: 'Sistema En Línea',
                /secure\s+connection/i: 'Conexión Segura',
                /target\s+met/i: 'Objetivo Cumplido',
            };
            
            for (const [pattern, replacement] of Object.entries(patterns)) {
                if (pattern.test(trimmed)) {
                    if (typeof replacement === 'function') {
                        const match = trimmed.match(pattern);
                        return replacement(...match);
                    }
                    return replacement;
                }
            }
        }
        
        // Return original if no translation found
        return text;
    }
    
    // Change language
    async setLanguage(lang) {
        if (this.translations[lang]) {
            this.currentLang = lang;
            localStorage.setItem('app_language', lang);
            
            // Reload page to apply translations cleanly
            window.location.reload();
            return true;
        }
        return false;
    }
    
    // Check if element should be translated
    shouldTranslate(element) {
        // Skip if has no-translate attribute
        if (element.hasAttribute('data-no-translate') || element.closest('[data-no-translate]')) {
            return false;
        }
        
        // Skip script, style, etc
        const skipTags = ['SCRIPT', 'STYLE', 'CODE', 'PRE'];
        if (skipTags.includes(element.tagName)) {
            return false;
        }
        
        return true;
    }
    
    // Translate a single element (sync for initial load)
    translateElement(element) {
        if (!this.shouldTranslate(element)) return;
        
        // Store original text if not stored yet
        if (!this.originalTexts.has(element)) {
            this.originalTexts.set(element, {
                text: element.textContent,
                placeholder: element.placeholder,
                ariaLabel: element.getAttribute('aria-label'),
                title: element.getAttribute('title')
            });
        }
        
        // Translate direct text nodes only
        for (let node of element.childNodes) {
            if (node.nodeType === Node.TEXT_NODE) {
                const text = node.textContent.trim();
                if (text) {
                    const translated = this.t(text);
                    if (translated !== text) {
                        // Preserve whitespace structure
                        const before = node.textContent.match(/^\s*/)[0];
                        const after = node.textContent.match(/\s*$/)[0];
                        node.textContent = before + translated + after;
                    }
                }
            }
        }
        
        // Translate attributes
        if (element.placeholder) {
            element.placeholder = this.t(element.placeholder);
        }
        
        if (element.hasAttribute('aria-label')) {
            const ariaLabel = element.getAttribute('aria-label');
            element.setAttribute('aria-label', this.t(ariaLabel));
        }
        
        if (element.hasAttribute('title')) {
            const title = element.getAttribute('title');
            element.setAttribute('title', this.t(title));
        }
    }
    
    // Translate entire page (sync fallback)
    translatePage() {
        // Translate all text elements
        const selectors = 'a, button, h1, h2, h3, h4, h5, h6, p, span, label, td, th, li, div, option';
        document.querySelectorAll(selectors).forEach(el => {
            this.translateElement(el);
        });
        
        // Translate inputs and textareas
        document.querySelectorAll('input[placeholder], textarea[placeholder]').forEach(el => {
            if (el.placeholder) {
                el.placeholder = this.t(el.placeholder);
            }
        });
    }
    
    // Translate entire page with API (async)
    async translatePageAsync() {
        if (this.currentLang === 'en') {
            // English is the default - no translation needed
            return;
        }
        
        // Use synchronous translation for reliability
        this.translatePage();
    }
    
    // Update language switcher UI
    updateLanguageSwitcher() {
        // Update dropdown button text
        const currentLangSpan = document.getElementById('currentLang');
        if (currentLangSpan) {
            currentLangSpan.textContent = this.currentLang === 'en' ? 'English' : 'Español';
        }
        
        // Update dropdown menu checkmarks
        document.querySelectorAll('.lang-option').forEach(btn => {
            const lang = btn.getAttribute('data-lang');
            const checkIcon = btn.querySelector('.check-icon');
            if (lang === this.currentLang) {
                checkIcon?.classList.remove('hidden');
            } else {
                checkIcon?.classList.add('hidden');
            }
        });
        
        // Update mobile select
        const mobileSelect = document.getElementById('mobileLangSelect');
        if (mobileSelect) {
            mobileSelect.value = this.currentLang;
        }
        
        // Update old style buttons if they exist
        document.querySelectorAll('[data-lang]').forEach(btn => {
            const lang = btn.getAttribute('data-lang');
            if (lang === this.currentLang) {
                btn.classList.add('bg-white/20', 'font-bold');
                btn.classList.remove('text-white/70');
            } else {
                btn.classList.remove('bg-white/20', 'font-bold');
                btn.classList.add('text-white/70');
            }
        });
    }
    
    // Watch for dynamic content
    observeDOM() {
        const observer = new MutationObserver(mutations => {
            mutations.forEach(mutation => {
                mutation.addedNodes.forEach(node => {
                    if (node.nodeType === Node.ELEMENT_NODE) {
                        this.translateElement(node);
                        node.querySelectorAll('*').forEach(child => {
                            this.translateElement(child);
                        });
                    }
                });
            });
        });
        
        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
    }
    
    // Initialize
    init() {
        // Translate on load
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', async () => {
                await this.translatePageAsync();
                this.updateLanguageSwitcher();
                this.observeDOM();
            });
        } else {
            // Already loaded
            this.translatePageAsync().then(() => {
                this.updateLanguageSwitcher();
                this.observeDOM();
            });
        }
        
        // Setup language switcher clicks
        document.addEventListener('click', async (e) => {
            // Handle dropdown toggle
            const languageBtn = document.getElementById('languageBtn');
            const languageMenu = document.getElementById('languageMenu');
            
            if (e.target.closest('#languageBtn')) {
                e.preventDefault();
                languageMenu?.classList.toggle('hidden');
                return;
            }
            
            // Close dropdown when clicking outside
            if (!e.target.closest('.language-dropdown')) {
                languageMenu?.classList.add('hidden');
            }
            
            // Handle language selection
            const langBtn = e.target.closest('[data-lang]');
            if (langBtn) {
                e.preventDefault();
                const lang = langBtn.getAttribute('data-lang');
                
                // Show loading state
                langBtn.style.opacity = '0.5';
                
                await this.setLanguage(lang);
                
                // Remove loading state
                langBtn.style.opacity = '1';
                
                // Close dropdown
                languageMenu?.classList.add('hidden');
            }
        });
        
        // Handle mobile select change
        document.addEventListener('change', async (e) => {
            if (e.target.id === 'mobileLangSelect') {
                const lang = e.target.value;
                e.target.style.opacity = '0.5';
                await this.setLanguage(lang);
                e.target.style.opacity = '1';
            }
        });
    }
}

// Initialize auto-translate with English as default
const autoTranslate = new AutoTranslate();
autoTranslate.init();

// Export globally
window.autoTranslate = autoTranslate;

