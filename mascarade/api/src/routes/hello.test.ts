import request from 'supertest';
import app from '../app';

describe('API Routes', () => {
    it('should return a greeting message', async () => {
        const response = await request(app).get('/api/hello');
        expect(response.status).toBe(200);
        expect(response.body.message).toBe('Hello, World!');
    });
});