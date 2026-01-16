function showSpinner(show) {
    const overlay = document.getElementById('spinner-overlay');
    if (!overlay) return;
    if (show) {
        overlay.classList.remove('hidden');
        overlay.classList.add('flex');
        // Simple CSS spinner - no external library needed
        if (!overlay.querySelector('.spinner')) {
            const spinner = document.createElement('div');
            spinner.className = 'spinner';
            spinner.innerHTML = '<div class="w-12 h-12 border-4 border-white border-t-transparent rounded-full animate-spin"></div>';
            overlay.appendChild(spinner);
        }
    } else {
        overlay.classList.add('hidden');
        overlay.classList.remove('flex');
    }
}

axios.interceptors.request.use((config) => {
    showSpinner(true);
    return config;
}, (error) => {
    showSpinner(false);
    return Promise.reject(error);
});

axios.interceptors.response.use((response) => {
    showSpinner(false);
    return response;
}, (error) => {
    showSpinner(false);
    return Promise.reject(error);
});

// Register Alpine.js components
// This will be called when Alpine.js fires the 'alpine:init' event
function registerAlpineComponents() {
    if (typeof Alpine === 'undefined') {
        return;
    }

    Alpine.data('registrationPage', () => ({
        activities: [],
        form: { name: '', classroom: '', number: '', activity_id: null },
        searchQuery: '',
        searchResults: [],
        async searchStudents() {
            if (this.searchQuery.length < 2) {
                this.searchResults = [];
                return;
            }
            try {
                const res = await axios.get('/api/search_students?q=' + encodeURIComponent(this.searchQuery));
                this.searchResults = res.data;
            } catch (e) {
                console.error('Search error', e);
            }
        },
        selectStudent(student) {
            this.form.name = student.name;
            this.form.number = student.number;
            this.form.classroom = student.classroom || '';
            this.searchQuery = `${student.number} - ${student.name}`;
            this.searchResults = [];
        },
        async loadActivities() {
            const res = await axios.get('/api/activities');
            this.activities = res.data;
        },
        groupedActivities() {
            const groups = {};
            this.activities.forEach(a => {
                const groupName = a.group_name || 'อื่นๆ (กิจกรรมทั่วไป)';
                if (!groups[groupName]) groups[groupName] = [];
                groups[groupName].push(a);
            });
            return groups;
        },
        selectActivity(activity) {
            if (activity.status !== 'open' || activity.remaining_seats <= 0) {
                Swal.fire('ไม่สามารถเลือกกิจกรรมนี้ได้', 'กิจกรรมปิดรับสมัครหรือเต็มแล้ว', 'warning');
                return;
            }
            this.form.activity_id = activity.id;
        },
        async submit() {
            if ((!this.form.name && !this.form.number) || !this.form.activity_id) {
                Swal.fire('กรุณากรอกข้อมูลให้ครบ', 'ต้องระบุชื่อ-สกุล หรือ เลขประจำตัวนักเรียน อย่างใดอย่างหนึ่ง', 'warning');
                return;
            }
            try {
                const res = await axios.post('/api/register', this.form);
                const data = res.data;
                if (data.success) {
                    Swal.fire('สำเร็จ', data.message, 'success');
                    this.form.activity_id = null;
                    await this.loadActivities();
                } else {
                    Swal.fire('ไม่สามารถลงทะเบียนได้', data.message, 'error');
                }
            } catch (e) {
                Swal.fire('ผิดพลาด', 'เกิดข้อผิดพลาดจากเซิร์ฟเวอร์', 'error');
            }
        },
        init() {
            this.loadActivities();
        }
    }));

    Alpine.data('adminLoginPage', () => ({
        username: '',
        password: '',
        async login() {
            const formData = new URLSearchParams();
            formData.append('username', this.username);
            formData.append('password', this.password);
            formData.append('grant_type', 'password');
            try {
                const res = await axios.post('/admin/login', formData);
                localStorage.setItem('adminToken', res.data.access_token);
                Toastify({ text: 'เข้าสู่ระบบสำเร็จ', backgroundColor: '#16a34a' }).showToast();
                window.location.href = '/admin/dashboard';
            } catch (e) {
                Swal.fire('เข้าสู่ระบบไม่สำเร็จ', 'ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง', 'error');
            }
        }
    }));
}

// Register when alpine:init fires (recommended way)
document.addEventListener('alpine:init', registerAlpineComponents);

// Also try immediately in case Alpine is already loaded
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', registerAlpineComponents);
} else {
    registerAlpineComponents();
}