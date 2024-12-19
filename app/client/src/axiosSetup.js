import axios from 'axios';

const axiosInstance = axios.create({
    baseURL: '/api',
    headers: {
        'Cf-Access-Jwt-Assertion': document.cookie
            .split('; ')
            .find(row => row.startsWith('CF_Authorization='))
            ?.split('=')[1]
    }
});

axiosInstance.interceptors.request.use(
    config => {
        const token = document.cookie
            .split('; ')
            .find(row => row.startsWith('CF_Authorization='))
            ?.split('=')[1];
        if (token) {
            config.headers['Cf-Access-Jwt-Assertion'] = token;
        }
        return Promise.resolve(config);
    },
    error => {
        return Promise.reject(error);
    }
);

export default axiosInstance;
