import http from 'k6/http';
import { sleep, check } from 'k6';

export const options = {
  vus: 10,
  duration: '120s',
};

export default function () {
  const url = 'http://localhost:8000/advertisement/simple_predict';
  const params = {
    headers: {
      'Content-Type': 'application/json',
      'accept': 'application/json'
    },
  };

  const rand = Math.random() * 100;

  let payload;

  if (rand < 70) {
    payload = JSON.stringify({ item_id: 10 });
    
  } else if (rand < 90) {
    payload = JSON.stringify({ item_id: 999999 });
    
  } else {
    payload = JSON.stringify({ item_id: -5 }); 
  }

  const res = http.post(url, payload, params);
  
  check(res, {
    'status is 200': (r) => r.status === 200,
    'status is 404': (r) => r.status === 404,
    'status is 422': (r) => r.status === 422,
  });

  sleep(0.1); 
}
