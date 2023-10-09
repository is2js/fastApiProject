//유틸리티 시작
function fetchPost(url, data = null) {
    return fetch(url, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "Accept": "application/json"
        },
        body: data ? JSON.stringify(data) : null,
    })
        .then(response => {
            if (response.ok) {
                // 204는 .json()을 못씀.
                // return response.json();
                return response.status === 204 ? true : response.json();
            } else {
                console.log(response.status);
                return false;
            }
        }).catch((error) => {
            console.error("Error:", error);
        });
}

function fetchGet(url, data = {}) {
    let query = '';
    if (Object.keys(data).length > 0) {
        query = '?' + Object.keys(data)
            .map(k => encodeURIComponent(k) + '=' + encodeURIComponent(data[k]))
            .join('&');
    }

    return fetch(url + query, {
        method: "GET",
        headers: {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    }).then(response => {
        if (response.ok) {
            return response.json();
        } else {
            console.log(response.status);
            return false;
        }
    }).catch((error) => {
        console.error("Error:", error);
    });
}

//유틸리티 끝